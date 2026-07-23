# Concept opérationnel — Quad4D en volière

*Dieynaba DIOP — juillet 2026 — document de travail (jet rédigé avec Claude, à valider)*

## 1. Contexte et mission

Quad4D fait voler plusieurs drones en même temps dans la volière de l'ENAC, pour
des shows chorégraphiés en intérieur. Les drones tournent sous Paparazzi et ne se
localisent pas par GPS : leur position vient du système de capture de mouvement
OptiTrack, injectée dans chaque drone par la liaison de données.

L'IHM Quad4D (Click'n Fly) est l'outil de l'opérateur pendant le show : elle
permet de choisir un scénario prédéfini ou d'en composer un à partir de la
bibliothèque de trajectoires, de suivre les drones en 3D et sur la télémétrie
live, et de piloter l'exécution. La sécurité entre drones repose sur la
conception des trajectoires elles-mêmes : les scénarios sont vérifiés hors
ligne (détection de conflits entre trajectoires) avant d'être volés.

En pratique, une session se fait avec un seul opérateur, qui a donc les mains
sur le clavier et les yeux qui alternent entre l'écran et la volière. Ce double
rôle est important : tout ce que le système lui demande de faire pendant le vol
doit être faisable sans quitter des yeux ce qui se passe derrière le filet.

## 2. Séquence nominale (existant)

Aujourd'hui, une session se déroule dans deux outils : Paparazzi (le Paparazzi
Center pour lancer la session, le GCS pour commander les drones) et l'IHM
Quad4D pour le show lui-même. Concrètement, voici la séquence, de l'arrivée en
volière au rangement :

| # | Étape | Outil |
|---|---|---|
| 1 | Placer les drones, batteries branchées, dans la volière | — (physique) |
| 2 | Allumer la radiocommande | — (physique) |
| 3 | Build des drones qui vont voler, lancement des opérations | Paparazzi Center |
| 4 | Vérifier que toutes les icônes sont vertes (OptiTrack, RC, XBee…) | GCS pprz |
| 5 | Démarrer les moteurs | GCS pprz |
| 6 | Décollage ; les drones montent et se mettent en holding point | GCS pprz |
| 7 | Lancer l'IHM, choisir ou composer le scénario, dérouler le show | IHM Quad4D |
| 8 | Faire atterrir les drones | GCS pprz |
| 9 | Couper les moteurs | GCS pprz |

L'étape 7 est la seule qui se passe dans l'IHM : tout l'encadrement du vol —
avant comme après — se fait dans le GCS. L'opérateur passe donc son temps à
« valser » entre deux fenêtres, et le paragraphe sur les exceptions montrera
que c'est au pire moment que cette valse coûte le plus cher.

À côté de cette séquence, deux réglages sont *persistants* : ils ne se refont
pas à chaque session, seulement quand quelqu'un a touché à la configuration.

- **Le fichier de télémétrie de chaque drone doit être `vto_wfb.xml`.** Le
  fichier générique `default_rotorcraft` est trop bavard : il sature la bande
  passante radio et étouffe l'uplink `EXTERNAL_POSE` qui porte la position
  OptiTrack — le drone dérive en vol alors que tout semble normal au sol.
- **Après un changement de configuration, il faut reflasher le drone**, sinon
  les settings embarqués ne correspondent plus à ceux que le sol croit envoyer.

## 3. Exceptions et conduite à tenir

Ce qui suit vient du vécu des sessions de juillet 2026 : ce sont les problèmes
réellement rencontrés, plus un cas jamais observé mais suffisamment critique
pour être anticipé.

| Exception | Comment on la détecte | Réponse aujourd'hui |
|---|---|---|
| Uplink saturé (mauvais fichier de télémétrie) | Dérive du drone en vol, difficile à diagnostiquer — l'affichage sol reste normal | Passer la télémétrie en `vto_wfb.xml`, c'est une config à vérifier *avant* de voler |
| Settings désynchronisés après un changement de conf | Erreur « No settings #… » dans le log pprz | Reflasher le drone |
| Pose OptiTrack absente au sol | Icône GPS rouge dans le GCS | Vérifier que le PC est sur le bon réseau et que le bon process NatNet tourne |
| Perte OptiTrack en plein vol | *(jamais observée à ce jour)* | Faire atterrir tout le monde immédiatement : sans mocap, les drones n'ont plus de position |
| Un ou deux drones deviennent erratiques en plein show | À l'œil, en regardant la volière | Retourner au GCS pour les faire atterrir, ou les kill en dernier recours |

La dernière ligne mérite qu'on s'y arrête, parce que c'est la situation la plus
stressante et celle qui dicte le plus d'exigences sur l'outillage.

**Land plutôt que kill.** Quand un drone déraille, deux réponses existent :
l'atterrissage commandé (le drone descend et se pose) et le kill (coupure
moteurs immédiate, le drone tombe). Le kill arrête le danger plus vite, mais
l'impact casse du matériel. La règle retenue est donc de faire atterrir par
défaut, et de réserver le kill aux cas où le drone met en danger quelque chose
de plus précieux que lui-même — typiquement s'il fonce vers le filet, un autre
drone, ou une personne.

**Le problème de la valse.** Aujourd'hui, land et kill vivent dans le GCS,
alors que pendant le show l'opérateur est dans l'IHM. Au moment précis où
chaque seconde compte, il faut retrouver l'autre fenêtre, retrouver le bon
drone dedans, et agir — tout en gardant un œil sur la volière. C'est le
principal défaut opérationnel du système actuel, et la motivation première du
concept cible.

## 4. Concept cible

Le principe tient en une phrase : **entre le lancement de la session Paparazzi
et le rangement, l'opérateur ne quitte plus l'IHM.** Le GCS reste ouvert
derrière, mais comme filet de secours, pas comme outil de travail.

La séquence cible devient :

1. Installation physique et radiocommande — inchangé.
2. Lancement de la session Paparazzi — inchangé (éventuellement scripté un
   jour, mais ce n'est pas là que ça fait mal).
3. Tout le reste dans l'IHM :
   - **une checklist pré-vol par drone** : pose mocap reçue, RC OK, batterie
     OK, settings synchronisés — l'équivalent des « icônes vertes » du GCS,
     mais au même endroit que le reste du show ;
   - **démarrer les moteurs**, **décoller** ;
   - dérouler le show comme aujourd'hui ;
   - **land all** en fin de show, puis **couper les moteurs** ;
   - et pendant tout le vol, des commandes d'urgence visibles en permanence :
     land all, et kill par drone en dernier recours.

Ce n'est plus un projet lointain : la chaîne est **implémentée dans l'IHM
opérateur et validée en simulation** (juillet 2026). L'IHM parle aux drones par
le bus Ivy — elle bascule le mode `auto2` en Guided via le gestionnaire de
settings, déclenche les blocs du plan de vol (démarrage moteurs, décollage,
atterrissage) par message `JUMP_TO_BLOCK`, coupe les moteurs par le setting
`kill_throttle`, et affiche une checklist par drone à partir des messages déjà
reçus (`ROTORCRAFT_STATUS`, `EXTERNAL_POSE`) : pose mocap, liaison RC, liaison
télémétrie et batterie, sous forme d'icônes vertes / jaunes / rouges reprenant
le langage visuel du GCS.

Concrètement, l'enchaînement se réduit à quelques boutons : un unique bouton
**Décoller** enchaîne démarrage moteurs → décollage → mise en place aux points
de standby fixes ; **Stop** ramène les drones à ces mêmes points ; **Land all**
les fait atterrir ; et **Kill**, par drone et avec confirmation à deux clics
(un kill accidentel fait tomber un drone), reste visible en permanence.

**Que fait le show quand un drone doit être posé ?** Sans évitement réactif
embarqué, rien ne garantit que la descente d'un drone ne croise pas la
trajectoire d'un autre. La règle est donc le land all : quand un drone doit se
poser, tout le monde se pose. Le land sélectif — poser le fautif pendant que
le show continue — reste une perspective, qui ne sera envisageable qu'avec une
garantie de non-croisement des descentes.

## 5. Limites et hypothèses

- **Règle batterie (implémentée, seuils à confirmer en vol).** L'IHM applique
  deux seuils de tension pack (3S) lus dans `ROTORCRAFT_STATUS` : *land-soon* à
  10,5 V (3,5 V/cellule) et *land-now* à 9,9 V (3,3 V/cellule). Trois effets :
  (1) une icône batterie verte / jaune / rouge par drone dans la checklist ;
  (2) **blocage au lancement** — si un pack est déjà sous le seuil land-soon, le
  show ne démarre pas et l'IHM demande de changer la batterie ; (3)
  **atterrissage automatique** — si un drone en vol passe sous le seuil
  land-now, un *land all* est déclenché. Il n'y a volontairement *pas*
  d'estimation « la batterie tiendra-t-elle jusqu'à la fin ? » : le show boucle
  indéfiniment, il n'existe donc pas de durée finie sur laquelle projeter la
  décharge. Les deux seuils restent théoriques et sont à confirmer en vol ; une
  estimation d'autonomie restante affichée *en information* (sans blocage) est
  une perspective.
- **Le GCS reste le secours.** Le concept cible déplace les commandes
  courantes vers l'IHM mais ne supprime rien : en cas de doute ou de panne de
  l'IHM, le GCS garde tous ses moyens d'action.
- **Une radiocommande par drone** : l'armement Paparazzi exige un lien RC
  actif ; sans lui, le passage en Guided est refusé silencieusement.
- **Pas d'évitement réactif pour le moment.** Un évitement réactif a été
  développé et réglé en simulation, mais il est débrayé à ce stade : la
  sécurité entre drones repose sur la vérification des trajectoires hors ligne
  et sur la vigilance de l'opérateur. Sa remise en service est une décision à
  part entière, hors du périmètre de ce document.
- **Le système dépend entièrement de l'OptiTrack.** Pas de mocap, pas de vol —
  il n'y a pas de solution de repli de localisation en intérieur.
- Les chiffres d'enveloppe (dimensions utiles de la volière, nombre maximal de
  drones simultanés, autonomie typique en vol) sont connus mais pas encore
  reportés ici — à compléter à la prochaine occasion.
