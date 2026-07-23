# Contribuer

Les contributions sont les bienvenues 🙌

1. Ouvrez une **issue** pour discuter des changements importants avant de coder.
2. **Forkez**, créez une branche, puis proposez une **Pull Request** vers `main`.
3. La CI (**hassfest** + **HACS**) doit passer.

## Développement local

Copiez `custom_components/sobry` dans le dossier `custom_components` d'une instance Home Assistant de test, puis redémarrez.

L'API Sobry est documentée sur [api.sobry.co/v2/docs](https://api.sobry.co/v2/docs).

## Règles

- Ne jamais inclure de clé API ou de secret dans un commit, un log ou une capture.
- Garder le code typé et idiomatique Home Assistant (`ruff`, `hassfest`).
