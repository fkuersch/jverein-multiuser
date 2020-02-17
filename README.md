# jverein-multiuser: jVerein mit mehreren Benutzern verwenden

Dieses Script bietet Multiuser-Support für jVerein mit beliebig vielen Nutzern.

[TOC]



## Features

### Multiuser-Support

Dieses Script bietet Multiuser-Support für jVerein mit beliebig vielen Nutzern. Dabei wird die Vereinsverwaltung für alle anderen Nutzer gesperrt, sobald ein Nutzer jVerein startet.

### Versionskontrolle

#### Nachvollziehbarkeit

Im Git-Repository kann nachvollzogen werden, wer wann welche Änderungen vorgenommen hat. Dazu hinterlässt jeder Nutzer nach jeder Änderung eine kurze Nachricht (commit message). Die Datenbanken werden außerdem als Text (SQL-Export) gespeichert.

#### Savepoints

Falls kritische Änderungen missglücken, kann man die Änderungen verwerfen und die gesamte Vereinsverwaltung wird zum vorherigen Stand zurückgesetzt. So kann man z. B. Updates oder Abrechnungen gefahrlos testen.

#### Externes Backup

Falls die lokalen Dateien verloren gehen oder beschädigt werden, ist eine weitere Version immer noch im Online-Repository. Es ist natürlich trotzdem sehr empfehlenswert, regelmäßig weitere Backups anzulegen.

### Export von E-Mail-Adressen

Die E-Mail-Adressen aller aktuellen Mitglieder werden in die Datei 'dump/mitglieder-emails.csv' exportiert.

Diese Liste kann verwendet werden, um die Abonnenten einer Mailingliste zu aktualisieren, z. B. mailman sync_members: http://manpages.org/sync_members/8



## Installation

### Voraussetzungen

* [Standardinstallation](https://doku.jverein.de/allgemein/installation) von Jameica, Hibiscus und jVerein mit mindestens Jameica 2.6.3, ggf. per [Jameica-Mashup](https://hibiscus-mashup.derrichter.de/)
  * Datenbank: H2 (Standard), nicht MySQL
* Python 3.8+




## SSH

* reduce key password requests by using ssh-agent

https://help.github.com/en/github/authenticating-to-github/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent#adding-your-ssh-key-to-the-ssh-agent



## Alternativen

Es gibt diverse alternative Ansätze, Multiuser-Fähigkeit für jVerein umzusetzen. Diese sind in der jVerein-Dokumentation beschrieben: https://doku.jverein.de/allgemein/multiuser