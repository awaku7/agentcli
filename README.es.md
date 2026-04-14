# uag (uagent)

uag es un agente de ejecución de herramientas de propósito general que se ejecuta en su entorno local. Interactúa con los usuarios a través de una interfaz de línea de comandos (CLI) y realiza diversas tareas como operaciones de archivos, búsqueda web y ejecución de scripts de Python según las instrucciones.

## Funciones Principales

- **Operaciones de archivos locales**: Lectura, escritura, edición y búsqueda de archivos.
- **Recuperación de información**: Búsqueda web con DuckDuckGo y extracción de contenido de páginas web.
- **Ejecución de código**: Ejecución segura de scripts de Python y comandos de PowerShell.
- **Procesamiento multimedia**: Generación de imágenes, lectura de archivos PDF/PPTX, capturas de pantalla.
- **Soporte multiidioma**: Admite varios idiomas, incluidos español, japonés e inglés.
- **Soporte MCP (Model Context Protocol)**: Puede conectarse a servidores MCP externos para ampliar sus funciones.

## Instalación

Puede instalarlo con pip desde PyPI:

```bash
pip install uag
```

Al iniciarse por primera vez, se iniciará automáticamente un asistente de configuración.

## Inicio Rápido

Después de la instalación, simplemente escriba el siguiente comando para comenzar:

```bash
uag
```

Una vez iniciado, puede pedirle al agente cosas como:
- "Lee el README en el directorio actual y resume su contenido."
- "Busca en la web las últimas noticias sobre IA y haz un resumen."
- "Comprime todos los archivos PNG en la carpeta 'images' en un archivo ZIP."

## Configuración (Variables de Entorno)

El comportamiento de uag se puede configurar a través de variables de entorno. Para más detalles, consulte:
- [ENVIRONMENT.md (English)](ENVIRONMENT.md)

## Documentación

- [README.md (English)](README.md)
- [README.ja.md (Japanese)](README.ja.md)

## Licencia

Publicado bajo la Licencia Apache 2.0.
