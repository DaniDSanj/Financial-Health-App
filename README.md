# Financial-Health-App
Aplicación multiplataforma para la gestión de las finanzas domésticas.

## Desarrollo

Tras clonar el repo, activa el hook local de pre-push (corre `ruff`/`ty`/`pytest` antes de cada
`git push`, replicando el CI — `core.hooksPath` no se versiona por Git, hay que activarlo una vez
por clon):

```bash
git config core.hooksPath .githooks
``` 
