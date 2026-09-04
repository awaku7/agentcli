# Compressão de contexto e contexto de modelo delimitado

O uag utiliza várias camadas para manter o contexto de modelo ativo delimitado. O objetivo é reduzir tokens de entrada desnecessários sem remover os ficheiros, os resultados das ferramentas ou os dados da sessão de que o utilizador ainda possa necessitar.

Este documento descreve a implementação atual. Distingue também o comportamento determinístico do comportamento específico do fornecedor ou do comportamento assistido pelo LLM.

## 1. Superfície dinâmica de ferramentas

Nem todas as definições de ferramentas precisam de ser enviadas para o modelo em cada turno.

- `tool_catalog` pesquisa as capacidades disponíveis.
- `tool_load` ativa apenas as ferramentas necessárias para a tarefa atual.
- `tool_catalog`, `tool_load` e `unload_tool` permanecem disponíveis como ferramentas de gestão.
- Os fluxos Responses API compatíveis com GPT-5.4 podem utilizar o Tool Search nativo do lado do servidor.
- O modo Tool Search legado restringe as especificações das ferramentas com `tool_catalog` no lado do cliente.

Isto reduz os tokens de entrada utilizados pelos esquemas das ferramentas, especialmente em instalações com muitas ferramentas.

## 2. Resultados textuais extensos das ferramentas tornam-se Artefactos

Quando um resultado textual de uma ferramenta excede o limiar de Artifact, o uag armazena o resultado completo como um Artifact e envia ao modelo uma referência limitada e uma pré-visualização, em vez do texto completo.

Os limites predefinidos são:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

A representação visível para o modelo contém o nome da ferramenta, o comprimento original, uma referência `artifact://`, o caminho de armazenamento e uma pré-visualização limitada. O resultado completo permanece disponível através do armazenamento Artifact.

O limiar pode ser alterado com `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Um valor de `0` desativa a promoção do Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` controla a política normal de resultados limitados; `0` desativa esse limite normal.

## 3. Recuperação limitada de `Artifact`

A ferramenta de infraestrutura `artifact_read` recupera apenas a parte solicitada de um `Artifact`:

- `start_line` seleciona a primeira linha.
- `max_lines` está limitado a 500.
- `max_chars` está limitado a 50 000 caracteres.
- Podem ser utilizados tanto um ID de Artifact como um URI de `artifact://`.

Isto permite inspecionar um pequeno intervalo relevante, em vez de reinjetar um ficheiro inteiro ou o resultado de um comando na próxima iteração do modelo.

Os novos artefactos são armazenados abaixo:

```text
~/.uag/artifacts/
```

Os caminhos Artifact legados existentes permanecem legíveis por motivos de compatibilidade.

## 4. Isolamento da carga binária

Os dados binários incorporados não são enviados como um resultado textual da ferramenta para a próxima iteração do modelo. Os campos com o formato Base64 são substituídos por um marcador curto, tal como:

```text
[carga binária omitida do contexto LLM]
```

A interface do utilizador e os clientes remotos continuam a poder receber anexos na memória, e os ficheiros guardados permanecem disponíveis através dos seus caminhos ou referências Artifact. Isto evita que imagens, áudio, capturas de ecrã e outras cargas binárias aumentem excessivamente o contexto textual do modelo.

A mesma classe de carga binária é sanitizada antes da persistência em SQLite e JSONL, impedindo que seja devolvida como uma carga de grandes dimensões após a recarga da sessão.

## 5. Compressão automática do histórico

O uag pode comprimir o histórico de conversas mais antigo quando a contagem de mensagens ou a contagem estimada de tokens atingir o limite configurado.

A política de compressão utiliza:

- o número de mensagens não pertencentes ao sistema;
- a janela de contexto resolvida do modelo, quando disponível;
- `UAGENT_SHRINK_KEEP_LAST` (20 por predefinição);
- `UAGENT_SHRINK_MAX_TOKENS` ou uma substituição específica do modelo;
- `UAGENT_SHRINK_CNT`; e
- `UAGENT_SHRINK_RATIO` (0,5 por predefinição quando a janela de contexto é conhecida).

Um limite específico do modelo pode ser fornecido da seguinte forma:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Um resumo anterior não é regenerado em cada turno. A histerese requer que se acumule um histórico novo suficiente, ou que ocorra outro estouro do orçamento de tokens, antes que a compressão seja executada novamente.

## 6. Resumos de histórico assistidos por LLM

Quando a compressão automática utiliza o LLM, as mensagens mais antigas do utilizador, do assistente e da ferramenta são resumidas numa mensagem de sistema contínua, enquanto a parte mais recente é mantida.

Históricos longos podem ser resumidos em blocos. Os controlos relevantes são:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

O resumo é avançado em vez de criar uma sequência ilimitada de mensagens de resumo. Esta é uma operação assistida por LLM e pode exigir pedidos adicionais ao fornecedor.

## 7. Compressão determinística de recurso

Se um resumo LLM não estiver disponível, o uag pode manter as mensagens do sistema iniciais e apenas as mensagens mais recentes. Os limites das chamadas de ferramentas são reparados para que o histórico resultante não comece nem termine com uma chamada de ferramenta órfã.

O carregador e o sanitizador também removem entradas irrelevantes para o modelo ou inválidas, incluindo mensagens exclusivas da interface do utilizador, mensagens de controlo interno, linhas de registo corrompidas, funções não suportadas, resultados de ferramentas órfãos e blocos de chamadas de ferramentas incompletos.

Quando uma sessão é recarregada, o prompt atual do sistema é restaurado e apenas as mensagens do sistema injetadas relevantes, tais como o contexto de skill ou hook, são retidas.

## 8. Recuperação de transbordamento de contexto

Se um fornecedor informar que a janela de contexto foi excedida, o uag identifica uma mensagem recente de grande tamanho no histórico e reverte essa mensagem e o histórico seguinte antes de tentar novamente. Trata-se de um recurso de fallback reativo, não de um substituto para a gestão normal de recursos.

## 9. Continuação e compactação do lado do fornecedor

Quando suportado, o Responses API utiliza `previous_response_id` para continuar uma cadeia de respostas sem reenviar todo o histórico de respostas gerido pelo fornecedor a partir do cliente.

Os fluxos Responses API também enviam a configuração de compactação do lado do fornecedor utilizando o mesmo limiar de redução local. O comportamento exato depende do fornecedor; o Artifact local e as políticas de histórico permanecem como salvaguardas independentes do fornecedor.

## 10. Eficiência na contagem de tokens

As contagens de tokens utilizadas para decisões de compressão são armazenadas em cache e atualizadas incrementalmente quando apenas novas mensagens forem adicionadas. Isto não reduz diretamente o contexto do modelo, mas reduz o custo da CPU e a latência na decisão de quando a compressão é necessária.

## O que ainda não é uma camada unificada completa

A implementação atual ainda não fornece todos os seguintes elementos como um gestor neutro em relação aos fornecedores:

- um `ContextManager` e um `ContextBudget` unificados;
- um `ToolResultRecord` com metadados de importância e evicção;
- resumos semânticos que não requeiram um `LLM`;
- recuperação e reinjeção automáticas de Artefactos relevantes;
- um Gestor de Resultados central que garanta a conversão `Artifact` para todas as ferramentas produtoras de binários; ou
- evicção sensível à prioridade em todas as categorias de sistema, histórico, esquema de ferramentas e resultados.

Em suma, o uag combina atualmente truncamento determinístico, referências a Artifact, isolamento de binários, seleção dinâmica de ferramentas, resumos do histórico, continuidade do fornecedor e recuperação de sobrecarga. O roteiro de conceção para uma camada de contexto unificada está documentado em [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
