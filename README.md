# Quad4D — Click'n Fly

Application de conduite de shows de drones en volière. Elle génère des
trajectoires chorégraphiées pour plusieurs quadrirotors, les déconflicte avant
le vol, et les fait voler depuis une interface unique : préparer, lancer,
suivre et arrêter le show sans passer par la ligne de commande.

Elle s'appuie sur l'autopilote [Paparazzi](https://github.com/paparazzi/paparazzi)
pour le vol et sur la bibliothèque [pat](https://github.com/poine/pat) pour les
trajectoires. La position des drones vient du système de capture de mouvement
de la volière, pas du GPS.

## Prérequis

Trois choses, à installer séparément — ce dépôt ne contient que l'application :

| | où le prendre |
|---|---|
| Python 3.10 ou plus | le gestionnaire de paquets du système |
| `pat`, le module `pat3` | <https://github.com/poine/pat> |
| Paparazzi, avec `sw/lib/python` | <https://github.com/paparazzi/paparazzi> |

Il faut également une volière équipée OptiTrack, diffusant des messages
`EXTERNAL_POSE`.

## Installation

**1. Python.** Vérifiez d'abord ce que vous avez :

```bash
python3 --version
```

S'il manque, ou s'il est antérieur à 3.10, sur Debian ou Ubuntu :

```bash
sudo apt install python3 python3-venv python3-pip
```

**2. La bibliothèque pat.** Elle n'est pas sur PyPI : on la clone, et on
déclarera son chemin à l'étape 4. L'emplacement est libre, `~/work/pat` est
la convention du laboratoire :

```bash
mkdir -p ~/work && git clone https://github.com/poine/pat.git ~/work/pat
```

Deux pièges à cet endroit :

- le dépôt s'appelle `pat`, le module Python `pat3` ;
- **le module est dans `src/`, pas à la racine.** C'est donc `pat/src` qu'il
  faudra mettre dans le `PYTHONPATH`, sans quoi l'import échoue alors même que
  le dépôt est bien cloné.

Ce n'est pas non plus le même dépôt que celui de cette application, bien que
tous deux soient d'Antoine Drouin.

**3. L'environnement Python.** Le lanceur cherche `~/venv_quad4d` par défaut :

```bash
python3 -m venv ~/venv_quad4d
source ~/venv_quad4d/bin/activate
pip install pyyaml numpy scipy matplotlib pyside6 numpy_stl pyqtgraph pyopengl ivy-python lxml
```

Si `pip` échoue sur `[Errno 101] Le réseau n'est pas accessible`, la machine
n'atteint pas PyPI. Le clonage de l'étape 2 peut très bien avoir réussi malgré
tout : il passe par SSH, alors que `pip` passe par HTTPS, et les deux ne sont
pas filtrés pareil. Cherchez un proxy avec `env | grep -i proxy`, et le cas
échéant ajoutez `--proxy http://LE_PROXY:PORT` à la commande `pip`.

**4. Les chemins vers pat et Paparazzi.** Un lancement par icône ne lit pas
votre `~/.bashrc` : le `PYTHONPATH` doit donc être déclaré dans un fichier
dédié, `~/.config/clicknfly.env`, que le lanceur charge à chaque démarrage.

```bash
mkdir -p ~/.config
cat > ~/.config/clicknfly.env <<'EOF'
export PYTHONPATH="$PYTHONPATH:$HOME/work/pat/src"
export PYTHONPATH="$PYTHONPATH:/chemin/vers/paparazzi/sw/lib/python"
export PAPARAZZI_HOME="/chemin/vers/paparazzi"
EOF
```

La première ligne suppose le clone de l'étape 2 ; adaptez-la si vous l'avez mis
ailleurs, et remplacez le chemin de Paparazzi par le vôtre. C'est l'erreur la
plus fréquente au premier lancement : sans ces chemins, l'application s'arrête
sur un `ModuleNotFoundError: pat3`.

Pour vérifier, sans quitter le venv :

```bash
source ~/.config/clicknfly.env && python3 -c "import pat3; print(pat3.__file__)"
```

Un mot sur les blocs `cat > ... <<'EOF'` : collés d'un seul tenant dans un
terminal, ils s'écrasent parfois sur une seule ligne et produisent un fichier
inutilisable, ou un `cat: export: Aucun fichier ou dossier de ce nom`. Si cela
arrive, écrivez le fichier avec un éditeur (`nano ~/.config/clicknfly.env`)
plutôt que de vous acharner au collage.

**5. L'icône de bureau.** Une seule commande, à lancer depuis la racine du
dépôt :

```bash
./install_launcher.sh
```

Elle écrit `~/.local/share/applications/clicknfly.desktop` avec des chemins
absolus résolus depuis l'emplacement du dépôt. « Click'n Fly » apparaît alors
dans le menu des applications, et peut être épinglé.

Le script résout tout seul le chemin du dépôt : si vous le lancez depuis un
autre clone, l'icône bascule vers celui-là. Il n'existe qu'une entrée de bureau,
la précédente est remplacée.

**6. Vérifier.** Fermez le terminal, ouvrez-en un neuf, et lancez par l'icône.
Elle doit démarrer dans un terminal qui n'a rien préparé : c'est le seul test
qui prouve que l'installation tient debout.

## Lancer

**Par l'icône**, et c'est la procédure d'exploitation. Le lanceur active le
venv et charge `clicknfly.env` lui-même, à chaque démarrage : il n'y a rien à
taper, et rien à préparer.

**En console**, il faut en revanche fournir soi-même ce que le lanceur fait
tout seul :

```bash
source ~/venv_quad4d/bin/activate
cd src/qt_gui && ./click_n_fly.py
```

Le venv et le `PYTHONPATH` sont des propriétés **du terminal**, pas de la
machine : ils disparaissent quand on le ferme, et un terminal neuf n'en sait
rien. C'est pourquoi l'icône fonctionne alors qu'un `./click_n_fly.py` lancé
dans une fenêtre fraîche échoue sur `ModuleNotFoundError: pat3` — les deux
chemins de lancement ne préparent pas le même environnement.

Pour ne plus avoir à y penser en console, faites charger les chemins par
chaque nouveau terminal, une fois pour toutes :

```bash
echo '[ -f "$HOME/.config/clicknfly.env" ] && . "$HOME/.config/clicknfly.env"' >> ~/.bashrc
```

Le venv, lui, reste à activer à la main : on ne veut pas qu'il s'impose à tous
les shells de la machine.

Options utiles :

| option | effet |
|---|---|
| `-v`, `--verbose` | détail de développement : mode de transit retenu, étagement, ordonnancement |
| `--scen NOM` | démarrer directement sur un scénario |

Sans `-v`, le journal reste à l'essentiel : avertissements et étapes clés.

**Un lancement par icône n'a pas de terminal où écrire.** En cas d'échec, une
fenêtre d'erreur apparaît, et le journal complet est dans :

```bash
tail -30 ~/.cache/clicknfly.log
```

## Avant un vol en volière

Trois points conditionnent une démonstration, et aucun n'est détecté par
l'application :

- **La configuration de télémétrie doit être allégée.** Avec la configuration
  par défaut, le volume de messages émis par les drones sature la liaison au
  détriment des positions issues de la capture de mouvement, et les commandes
  ne passent plus correctement.
- **Chaque drone doit être appairé à sa propre radiocommande.** C'est une
  exigence de sécurité : sans elle, le drone ne vole pas.
- **Chaque drone doit embarquer le bon firmware** pour accepter le mode guidé,
  faute de quoi il reste en mode NAV. Le cas échéant, reprogrammer l'autopilote.

Les seuils de batterie ne sont pas dans le code : ils sont lus dans la section
`BAT` du fichier `airframe` de chaque drone, celui-là même qu'utilise
l'autopilote. Changer un seuil ne demande donc aucune modification du logiciel.

## Où trouver quoi

| chemin | contenu |
|---|---|
| `src/qt_gui/click_n_fly.py` | l'application |
| `src/qt_gui/traj_factory.py` | les figures |
| `src/qt_gui/scenarios.py` | les scénarios prédéfinis |
| `src/qt_gui/spatial_deconfliction.py` | la déconfliction par ordonnancement |
| `src/qt_gui/data/` | scénarios composés par l'opérateur, propres à la machine |
| `docs/concept_operationnel.md` | le concept d'opérations |
| `docs/trajectories.md` | les trajectoires |
| `docs/TODO.md` | les chantiers ouverts |

Les fichiers de `src/qt_gui/data/` sont exclus du suivi de version : ils sont
locaux à chaque installation. Un nouveau clone démarre donc sans les scénarios
personnalisés du précédent.
