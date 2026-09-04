# Compressão de contexto e contexto de modelo delimitado

O uag utiliza várias camadas para manter o contexto de modelo ativo delimitado. O objetivo é reduzir tokens de entrada desnecessários sem remover os arquivos, resultados de ferramentas ou dados de sessão dos quais o usuário ainda possa precisar.

Este documento descreve a implementação atual. Ele também distingue o comportamento determinístico do comportamento específico do provedor ou assistido pelo LLM.

## 1. Superfície dinâmica de ferramentas

Nem toda definição de ferramenta precisa ser enviada ao modelo a cada turno.

- `tool_catalog` pesquisa os recursos disponíveis.
- `tool_load` habilita apenas as ferramentas necessárias para a tarefa atual.
- `tool_catalog`, `tool_load` e `unload_tool` permanecem disponíveis como ferramentas de gerenciamento.
- Fluxos Responses API compatíveis com GPT-5.4 podem usar o Tool Search nativo do lado do servidor.
- O modo Tool Search legado restringe as especificações das ferramentas com `tool_catalog` no lado do cliente.

Isso reduz os tokens de entrada usados pelos esquemas das ferramentas, especialmente em instalações com muitas ferramentas.

## 2. Resultados textuais extensos de ferramentas tornam-se Artefatos

Quando o resultado textual de uma ferramenta excede o limite de Artifact, o uag armazena o resultado completo como um Artifact e envia ao modelo uma referência limitada e uma pré-visualização, em vez do texto completo.

Os limites padrão são:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

A representação visível ao modelo contém o nome da ferramenta, o comprimento original, uma referência `artifact://`, o caminho de armazenamento e uma pré-visualização limitada. O resultado completo permanece disponível por meio do armazenamento do Artifact.

O limite pode ser alterado com `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Um valor de `0` desativa a promoção do Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` controla a política padrão de resultados limitados; `0` desativa esse limite padrão.

## 3. Recuperação limitada de `Artifact`

A ferramenta de infraestrutura `artifact_read` recupera apenas a parte solicitada de um `Artifact`:

- `start_line` seleciona a primeira linha.
- `max_lines` está limitado a 500.
- `max_chars` está limitado a 50.000 caracteres.
- É possível usar tanto um ID de Artifact quanto um URI de `artifact://`.

Isso permite inspecionar um pequeno intervalo relevante, em vez de reinserir um arquivo inteiro ou o resultado de um comando na próxima iteração do modelo.

Novos artefatos são armazenados abaixo:

```text
~/.uag/artifacts/
```

Os caminhos Artifact legados existentes permanecem legíveis por motivos de compatibilidade.

## 4. Isolamento de carga binária

Dados binários embutidos não são enviados como um resultado textual da ferramenta para a próxima iteração do modelo. Campos com formato Base64 são substituídos por um marcador curto, como:

```text
[carga binária omitida do contexto LLM]
```

A interface do usuário e os clientes remotos ainda podem receber anexos na memória, e os arquivos salvos permanecem disponíveis por meio de seus caminhos ou referências Artifact. Isso evita que imagens, áudio, capturas de tela e outras cargas binárias aumentem excessivamente o contexto textual do modelo.

A mesma classe de carga binária é sanitizada antes da persistência em SQLite e JSONL, impedindo que ela retorne como uma carga grande após a recarga da sessão.

## 5. Compressão automática do histórico

uag pode comprimir o histórico de conversas mais antigas quando a contagem de mensagens ou a contagem estimada de tokens atingir o limite configurado.

A política de compressão utiliza:

- o número de mensagens que não são do sistema;
- a janela de contexto resolvida do modelo, quando disponível;
- `UAGENT_SHRINK_KEEP_LAST` (20 por padrão);
- `UAGENT_SHRINK_MAX_TOKENS` ou uma substituição específica do modelo;
- `UAGENT_SHRINK_CNT`; e
- `UAGENT_SHRINK_RATIO` (0,5 por padrão quando uma janela de contexto é conhecida).

Um limite específico do modelo pode ser fornecido da seguinte forma:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Um resumo anterior não é regenerado a cada turno. A histerese requer que se acumule histórico novo suficiente, ou que ocorra outro estouro do orçamento de tokens, antes que a compactação seja executada novamente.

## 6. Resumos de histórico assistidos por LLM

Quando a compactação automática usa o LLM, as mensagens mais antigas do usuário, do assistente e da ferramenta são resumidas em uma mensagem de sistema contínua, enquanto a parte mais recente é mantida.

Históricos longos podem ser resumidos em blocos. Os controles relevantes são:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

O resumo é adiantado, em vez de criar uma sequência ilimitada de mensagens de resumo. Essa é uma operação assistida por LLM e pode exigir solicitações adicionais ao provedor.

## 7. Compressão determinística de fallback

Se um resumo LLM não estiver disponível, o uag pode manter as mensagens do sistema iniciais e apenas as mensagens mais recentes. Os limites das chamadas de ferramentas são reparados para que o histórico resultante não comece nem termine com uma chamada de ferramenta órfã.

O carregador e o sanitizador também removem entradas irrelevantes para o modelo ou inválidas, incluindo mensagens exclusivas da interface do usuário, mensagens de controle interno, linhas de log corrompidas, funções não suportadas, resultados de ferramentas órfãos e blocos incompletos de chamadas de ferramentas.

Quando uma sessão é recarregada, o prompt atual do sistema é restaurado e apenas as mensagens do sistema injetadas relevantes, como contexto de skill ou hook, são mantidas.

## 8. Recuperação de estouro de contexto

Se um provedor relatar que a janela de contexto foi excedida, o uag identifica uma mensagem recente de grande tamanho no histórico e reverte essa mensagem e o histórico subsequente antes de tentar novamente. Trata-se de um recurso de fallback reativo, não um substituto para o gerenciamento normal de recursos.

## 9. Continuação e compactação no lado do provedor

Quando suportado, o Responses API usa `previous_response_id` para continuar uma cadeia de respostas sem reenviar todo o histórico de respostas gerenciado pelo provedor a partir do cliente.

Os fluxos Responses API também enviam a configuração de compactação do lado do provedor usando o mesmo limite de redução local. O comportamento exato depende do provedor; o Artifact local e as políticas de histórico permanecem como salvaguardas independentes do provedor.

## 10. Eficiência na contagem de tokens

As contagens de tokens usadas para decisões de compactação são armazenadas em cache e atualizadas incrementalmente quando apenas novas mensagens forem adicionadas. Isso não reduz diretamente o contexto do modelo, mas diminui o custo de CPU e a latência na decisão de quando a compactação é necessária.

## O que ainda não é uma camada unificada completa

A implementação atual ainda não oferece todos os itens a seguir como um gerenciador neutro em relação ao provedor:

- um `ContextManager` e um `ContextBudget` unificados;
- um `ToolResultRecord` com metadados de importância e evicção;
- resumos semânticos que não exijam um `LLM`;
- recuperação e reinjeção automáticas de artefatos relevantes;
- um gerenciador central de resultados que garanta a conversão de `Artifact` para todas as ferramentas que produzem binários; ou
- evicção com consideração de prioridade em todas as categorias de sistema, histórico, esquema de ferramenta e resultados.

Em resumo, o uag combina atualmente truncamento determinístico, referências a Artifact, isolamento binário, seleção dinâmica de ferramentas, resumos de histórico, continuação do provedor e recuperação de estouro. O roteiro de projeto para uma camada de contexto unificada está documentado em [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
