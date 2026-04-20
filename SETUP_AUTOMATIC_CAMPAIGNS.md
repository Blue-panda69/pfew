# 🚀 Configuration du Serveur - Campagnes Automatiques

## Problème Résolu
Les campagnes s'exécutent maintenant **automatiquement** sans avoir besoin de rafraîchir les pages admin. Le système fonctionne en arrière-plan tant que le serveur Django est actif.

## Architecture

### 1. **APScheduler** (Automatique - Recommandé)
- ✓ Résultat: Les campagnes se déclenchent toutes les **10 secondes** sans intervention
- ✓ Pas besoin de terminal supplémentaire
- ✓ Compte SMTP mis à jour immédiatement dans les listes déroulantes
- ✓ Intégré au serveur `runserver`

**Utilisation :**
```bash
python manage.py runserver
```
Au démarrage, vous verrez :
```
✓ Campaign scheduler started (checking every 10 seconds)
```

### 2. **Management Command** (Alternatif - Manuel)

#### Option A: Exécution unique
```bash
python manage.py send_pending_campaigns
```
Envoie toutes les campagnes dues une seule fois.

#### Option B: En tant que daemon
```bash
python manage.py send_pending_campaigns --daemon
```
Lance une boucle continue qui vérifie les campagnes toutes les 10 secondes.
Arrêtez avec `Ctrl+C`.

---

## Flux de Travail

### Ajouter un Compte SMTP
1. Allez sur `http://127.0.0.1:8000/admin/core/smtpaccount/add/`
2. Remplissez les détails Gmail (générez le mot de passe d'application via les liens fournis)
3. Cliquez sur **Enregistrer**
4. ✓ Les comptes **actifs** apparaissent immédiatement dans le dropdown des campagnes

### Créer une Campagne
1. Allez sur `http://127.0.0.1:8000/admin/core/campaign/add/`
2. Sélectionnez un compte d'envoi SMTP (**requis**)
3. Définissez la date/heure de démarrage et fin
4. Sélectionnez des cibles et un modèle d'email
5. Cliquez sur **Enregistrer**

### Exécution Automatique
- À la date/heure de démarrage, le système :
  - ✓ Envoie les emails à toutes les cibles
  - ✓ Utilise les credentials du compte SMTP sélectionné
  - ✓ Marque les cibles comme envoyées
  - ✓ Change le statut à "Running" puis "Finished"
- **Aucune intervention nécessaire** - même si vous n'êtes pas sur la page admin

---

## Fichiers Modifiés

### `core/apps.py` - APScheduler
Initialise APScheduler au démarrage du serveur :
- Lance un job toutes les 10 secondes
- Appelle `send_pending_campaigns_task()` en arrière-plan
- Gère les connexions de base de données

### `core/tasks.py` - Logique des Campagnes
Contient la logique centrale d'exécution :
- `send_pending_campaigns_task()` - Trouve et déclenche les campagnes dues
- `_send_campaign_now()` - Envoie les emails d'une campagne
- Gère les erreurs et génère les logs

### `core/forms.py` - Formulaires
- `SmtpAccountForm` - Affiche les instructions détaillées pour générer les mots de passe (en français)
- `CampaignForm` - Dropdown dynamique qui se met à jour à chaque chargement

### `core/management/commands/send_pending_campaigns.py`
Management command pour exécution manuelle ou cron :
- `--daemon` - Mode boucle continue
- Logs en temps réel des campagnes envoyées

---

## Paramètres Configurables

### Intervalle de Vérification
Modifier dans `core/apps.py` :
```python
IntervalTrigger(seconds=10)  # Changez 10 en autre valeur (en secondes)
```

**Recommandations :**
- `5 secondes` - Haute réactivité (plus lourd)
- `10 secondes` - Équilibre (défaut)
- `30 secondes` - Faible consommation CPU

---

## Logs et Débogage

### Voir les Logs APScheduler
Le serveur affiche en temps réel :
```
✓ Campaign scheduler started (checking every 10 seconds)
✓ Campaign 'Phishing Test' started: 5 sent, 0 failed
✓ Campaign 'Phishing Test' marked as finished
❌ Failed to send to user@example.com: [erreur]
```

### Utiliser le Daemon en Arrière-Plan (Linux/Mac)
```bash
python manage.py send_pending_campaigns --daemon &
```

### Tâche Cron (Alternative)
Ajouter au crontab :
```cron
*/10 * * * * cd /chemin/vers/projet && python manage.py send_pending_campaigns
```
Exécute la vérification toutes les 10 minutes.

---

## Dépannage

### "Campaign scheduler ne démarre pas"
- Vérifiez que `django_apscheduler` est installé : `pip install django-apscheduler`
- Vérifiez que `INSTALLED_APPS` contient `'django_apscheduler'`

### Les campagnes ne s'exécutent pas
- Vérifiez que le serveur est actif : `python manage.py runserver`
- Vérifiez les logs du serveur pour les erreurs
- Assurez-vous qu'une SmtpAccount active existe
- Testez manuellement : `python manage.py send_pending_campaigns`

### Le dropdown SMTP est vide
- Créez au moins une SmtpAccount active
- Rechargez la page d'ajout de campagne (GET request récent)

---

## Structure des Fichiers Créés
```
core/
  ├── tasks.py                           # Logique des campagnes
  ├── apps.py                           # APScheduler
  ├── forms.py                          # Formulaires (mise à jour)
  └── management/
      ├── __init__.py
      └── commands/
          ├── __init__.py
          └── send_pending_campaigns.py # Management command
```

---

## Résumé des Améliorations

| Avant | Après |
|-------|-------|
| Campagnes = Besoin de rafraîchir admin | ✓ Automatiques sans intervention |
| Compte SMTP = Visible uniquement après rafraîchissement | ✓ Immédiatement disponible |
| Emails manuels par la page changelist | ✓ Envoyés en arrière-plan |
| Impossible de savoir quand ça s'exécute | ✓ Logs en temps réel |

Enjoy! 🎉
