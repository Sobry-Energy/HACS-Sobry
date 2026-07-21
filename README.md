<div align="center">

<img src="assets/banner.svg" alt="Sobry pour Home Assistant — l'électricité au juste prix, au bon moment" width="100%">

<br><br>

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-e7703d?style=flat-square)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-e7703d?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![Release](https://img.shields.io/github/v/release/Sobry-Energy/HACS-Sobry?style=flat-square&color=e7703d)](https://github.com/Sobry-Energy/HACS-Sobry/releases)
[![Licence MIT](https://img.shields.io/badge/Licence-MIT-201e21?style=flat-square)](LICENSE)
[![Maintenu par Sobry](https://img.shields.io/badge/maintenu%20par-Sobry-201e21?style=flat-square)](https://sobry.co)

</div>

---

## Sommaire

- [Présentation](#présentation)
- [Fonctionnalités](#-fonctionnalités)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Obtenir votre clé API](#-obtenir-votre-clé-api)
- [Configuration](#-configuration)
- [Entités créées](#-entités-créées)
- [Comprendre les paliers de prix](#-comprendre-les-paliers-de-prix)
- [Exemple d'automatisation](#-exemple-dautomatisation)
- [Sécurité & confidentialité](#-sécurité--confidentialité)
- [Gérer ou révoquer votre clé](#-gérer-ou-révoquer-votre-clé)
- [Dépannage](#-dépannage)
- [Feuille de route](#-feuille-de-route)

---

## Présentation

[Sobry](https://sobry.co) est un fournisseur d'électricité **dynamique** : le prix du kWh change **tous les quarts d'heure** en fonction du marché. Consommer au bon moment (lave-linge, recharge VE, ballon d'eau chaude…) fait baisser la facture — et c'est exactement là que Home Assistant devient utile.

Cette intégration **officielle** expose le prix de votre contrat, quart d'heure par quart d'heure, comme une entité Home Assistant. Vous pouvez alors déclencher vos appareils quand l'électricité est la moins chère (ou la plus verte), automatiquement.

> Éditée par **Sobry (YENKA ENERGIE SAS)**. Elle utilise l'**API publique Sobry** (`api.sobry.co`) via une **clé API en lecture seule** que vous générez depuis votre espace client.

## ✨ Fonctionnalités

- 🔌 **Prix en temps réel** du quart d'heure courant, en €/kWh **TTC** (exactement le tarif que vous payez).
- 🗓️ **Prix à venir** : les prochaines heures sont exposées en attribut, prêtes pour vos graphiques et vos automatisations anticipées.
- 🎨 **Palier de prix du créneau** (`GREEN`, `ORANGE`, `RED`, `DARK_GREEN`) pour des automatisations lisibles.
- 🔐 **Lecture seule, moindre privilège** : la clé n'autorise que la lecture des prix de votre contrat. Elle ne peut **rien modifier** sur votre compte.
- 🏠 **Multi-contrat** : gérez plusieurs contrats (résidence principale, secondaire…), un par un.
- 🇫🇷 Interface en français (et anglais).

## 📦 Prérequis

- **Home Assistant** 2024.12 ou plus récent.
- **[HACS](https://hacs.xyz/)** installé (recommandé pour l'installation et les mises à jour).
- Un **contrat Sobry actif**.
- Une **clé API** générée depuis votre espace client (voir plus bas — 2 minutes).

## 🔧 Installation

### Via HACS (recommandé)

[![Ouvrir dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Sobry-Energy&repository=HACS-Sobry&category=integration)

1. HACS → **Intégrations** → menu ⋮ → **Dépôts personnalisés**.
2. Ajoutez `https://github.com/Sobry-Energy/HACS-Sobry` — catégorie **Intégration**.
3. Cherchez **Sobry**, installez, puis **redémarrez Home Assistant**.

### Manuelle

1. Téléchargez la dernière [release](https://github.com/Sobry-Energy/HACS-Sobry/releases).
2. Copiez le dossier `custom_components/sobry` dans le dossier `custom_components` de votre configuration Home Assistant.
3. Redémarrez Home Assistant.

## 🔑 Obtenir votre clé API

La clé se génère en libre-service depuis votre espace client Sobry :

1. Connectez-vous à **[app.sobry.co](https://app.sobry.co)**.
2. **Sélectionnez le contrat** concerné (sélecteur en haut de page).
3. Allez dans **Profil** → section **« Clé API / Accès développeur »**.
4. Cliquez sur **« Générer une clé »**.
5. **Copiez la clé** (elle commence par `sob_apikey_`) : ⚠️ elle n'est affichée **qu'une seule fois**, cochez « J'ai copié la clé » avant de fermer.

> **Bon à savoir**
> - **1 clé = 1 contrat.** Pour plusieurs contrats, répétez l'opération et créez une clé par contrat.
> - **Portée : lecture des prix uniquement** (`price:read`). La clé ne peut pas modifier votre contrat, vos coordonnées bancaires, ni vos factures.
> - **Validité : 1 an.** À l'approche de l'échéance, régénérez une clé et mettez-la à jour dans Home Assistant.
> - **Révocable à tout moment** depuis le même écran (bouton « Révoquer »), effet immédiat.

## 🧩 Configuration

[![Ajouter l'intégration Sobry](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=sobry)

1. **Paramètres** → **Appareils et services** → **Ajouter une intégration** → cherchez **Sobry**.
2. **Collez votre clé API** (`sob_apikey_…`) et validez.
3. L'intégration vérifie la clé, puis crée automatiquement l'appareil et son entité.

C'est tout — **rien d'autre à saisir** : la clé étant liée à un seul contrat, le contrat est reconnu automatiquement.

**Plusieurs contrats ?** Ajoutez à nouveau l'intégration avec chaque clé : chaque contrat apparaît comme un appareil distinct.

## 📊 Entités créées

Pour chaque contrat configuré (un appareil **Sobry**) :

| Entité | Exemple d'`entity_id` | Unité | Description |
|---|---|---|---|
| **Prix actuel** | `sensor.sobry_prix_actuel` | €/kWh | Prix TTC du quart d'heure en cours. |

**Attributs de `sensor.sobry_prix_actuel` :**

| Attribut | Description |
|---|---|
| `palier` | Palier tarifaire du créneau : `GREEN`, `ORANGE`, `RED` ou `DARK_GREEN`. |
| `palier_couleur` | Code couleur hexadécimal du palier (fourni par l'API). |
| `prix_a_venir` | Liste horodatée des prix des prochains créneaux (24 h à venir). |

> **Rafraîchissement :** le prix est mis à jour à chaque quart d'heure (minutes 0, 15, 30, 45) ; les prix du lendemain sont récupérés en début d'après-midi. Les appels réseau sont mis en cache pour rester légers (~1 à 2 appels par jour).

## 🎨 Comprendre les paliers de prix

Chaque créneau de 15 minutes reçoit un **palier** selon son prix relatif sur la journée. Idéal pour piloter vos appareils sans manipuler de seuils en euros.

| Palier | Couleur | Quand |
|---|---|---|
| `DARK_GREEN` | 🟢 vert foncé (`#1B5E20`) | Prix négatif — l'électricité est à son plus bas. |
| `GREEN` | 🟩 vert (`#6CC264`) | Les **6 heures les moins chères** de la journée. |
| `ORANGE` | 🟧 orange (`#F0A631`) | Créneaux intermédiaires (par défaut). |
| `RED` | 🟥 rouge (`#F03131`) | Les **6 heures les plus chères** de la journée. |

## 🤖 Exemple d'automatisation

Lancer la recharge de la voiture uniquement quand le prix passe sous un seuil :

```yaml
automation:
  - alias: "Recharge VE quand l'électricité est bon marché"
    trigger:
      - platform: numeric_state
        entity_id: sensor.sobry_prix_actuel
        below: 0.15          # €/kWh
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.prise_voiture
```

Variante « créneaux les moins chers » (palier vert) :

```yaml
    trigger:
      - platform: state
        entity_id: sensor.sobry_prix_actuel
        attribute: palier
        to: "GREEN"
```

Vous pouvez aussi tracer la courbe des prix à venir avec [ApexCharts Card](https://github.com/RomRider/apexcharts-card) à partir de l'attribut `prix_a_venir`.

## 🔒 Sécurité & confidentialité

Cette intégration est pensée pour être **sûre par conception** :

- **Moindre privilège.** La clé API a la portée `price:read` et est **limitée à un seul contrat**. Elle ne permet **que** de lire vos prix — aucune écriture, aucun accès à vos moyens de paiement ou à vos factures, aucune capacité à créer ou gérer d'autres clés.
- **Stockage local.** La clé est conservée par Home Assistant dans sa configuration ; elle n'est **jamais écrite dans les journaux** et apparaît **masquée** dans les diagnostics exportables.
- **Révocation immédiate.** À tout moment, révoquez la clé depuis votre espace client : l'accès est coupé instantanément. Si Home Assistant détecte une clé invalide, il vous propose d'en **saisir une nouvelle** sans supprimer votre configuration.
- **Aucun tiers.** L'intégration communique **exclusivement** avec l'API officielle Sobry (`https://api.sobry.co`), en HTTPS. Aucune donnée n'est envoyée ailleurs.

## 🔄 Gérer ou révoquer votre clé

Tout se passe dans votre espace client (**app.sobry.co → contrat → Profil → Clé API**) :

- **Régénérer** : crée une nouvelle clé et **révoque automatiquement l'ancienne**. Pensez à mettre à jour Home Assistant (l'intégration vous le proposera au prochain échec d'authentification).
- **Révoquer** : coupe immédiatement tout accès. L'entité passera en `indisponible`.

## ❓ Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| L'entité est `indisponible` | Clé expirée, révoquée ou régénérée | Générez une nouvelle clé et mettez-la à jour dans Home Assistant (reconfiguration). |
| « Clé invalide » à la configuration | Copier-coller incomplet | Recopiez la clé entière (préfixe `sob_apikey_` inclus). |
| Un seul contrat visible | 1 clé = 1 contrat | Créez une clé par contrat et ajoutez l'intégration autant de fois. |

Un problème persistant ? Ouvrez une [issue](https://github.com/Sobry-Energy/HACS-Sobry/issues) (sans jamais y coller votre clé).

## 🚀 Feuille de route

- 🔐 **Connexion OAuth native** (sans clé à copier, avec révocation depuis Sobry).
- 📊 **Capteurs de suivi** (consommation et coût du mois) — dès que la portée de la clé le permettra.
- 🔔 Capteurs « prochain créneau vert » et « meilleur moment des prochaines 24 h ».
- 📈 Intégration au tableau de bord Énergie de Home Assistant.

## 🧰 Développement

```bash
git clone https://github.com/Sobry-Energy/HACS-Sobry.git
# copiez custom_components/sobry dans le config d'une instance HA de test
```

L'API Sobry utilisée est documentée sur **[api.sobry.co/v2/docs](https://api.sobry.co/v2/docs)**. Contributions bienvenues : issues et pull requests.

## 📄 Licence

Distribué sous licence [MIT](LICENSE). © 2026 YENKA ENERGIE SAS (Sobry).

## 🙏 Remerciements

Merci à la communauté Home Assistant francophone pour ses retours et ses idées.

---

<div align="center">
<sub>Fait avec ⚡ par <a href="https://sobry.co">Sobry</a> — l'électricité au juste prix, au bon moment.</sub>
</div>
