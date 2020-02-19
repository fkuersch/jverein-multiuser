# jverein-multiuser: jVerein mit mehreren Benutzern verwenden

jverein-multiuser bietet Multiuser-Support für jVerein mit beliebig vielen Nutzern. Dafür werden die gesamten Jameica-Daten mit dem Versionskontrollsystem Git verwaltet und in einem Online-Repository gespeichert.

[TOC]



## Features

### Multiuser-Support

Dieses Script bietet Multiuser-Support für jVerein mit beliebig vielen Nutzern. Dabei wird die Vereinsverwaltung für alle anderen Nutzer gesperrt, sobald ein Nutzer jVerein startet. Sollte jVerein bereits durch eine andere Person gesperrt sein, wird eine Meldung mit deren Namen angezeigt.

### Versionskontrolle

#### Nachvollziehbarkeit

Im Git-Repository kann nachvollzogen werden, wer wann welche Änderungen vorgenommen hat. Dazu hinterlässt jeder Nutzer nach jeder Änderung eine kurze Nachricht (commit message). Die Datenbanken werden als Text (SQL-Export) gespeichert, was die Nachvollziehbarkeit von Änderungen erleichtert.

#### Savepoints

Falls kritische Änderungen missglücken, kann man die Änderungen verwerfen und die gesamte Vereinsverwaltung wird zum vorherigen Stand zurückgesetzt. So kann man z. B. Updates oder Abrechnungen gefahrlos testen.

#### Externes Backup

Falls die lokalen Dateien verloren gehen oder beschädigt werden, ist eine weitere Version immer noch im Online-Repository vorhanden (inklusive der gesamten Historie). Es ist natürlich trotzdem sehr empfehlenswert, regelmäßig weitere Backups anzulegen - ggf. auch automatisch über das Online-Repository.

### Export von E-Mail-Adressen

Die E-Mail-Adressen aller aktuellen Mitglieder werden in die Datei 'dump/mitglieder-emails.csv' exportiert.

Diese Liste kann verwendet werden, um die Abonnenten einer Mitglieder-Mailingliste zu aktualisieren, z. B. mit mailman sync_members: http://manpages.org/sync_members/8



## FAQ - Häufige Fragen

### An wen richtet sich jverein-multiuser?



### Ist jverein-multiuser sicher?

Nein. Fast alle Daten im Repository sind unverschlüsselt. Konfigurationsdateien und die jVerein-Datenbank sind ohnehin nicht verschlüsselt, zusätzlich werden alle Datenbanken als Klartext im Repository abgelegt und dazu ggf. entschlüsselt.

Da das Repository sensible Mitglieder- und Finanzdaten enthält, ist es umso wichtiger, selbst für die Sicherheit der Daten zu sorgen. Hier einige Tipps (wie die genau umgesetzt werden können, sprengt allerdings den Rahmen dieser Dokumentation):

Online- und Offline-Repositories auf einer verschlüsselten Festplatte oder in einem verschlüselten Container speichern, aktuelle Anti-Viren-Software verwenden, Online-Repository nur für die Nutzer von jVerein verfügbar machen, nur Zugang per SSH erlauben, dabei Passwort-Authentifizierung abschalten, nur Key-basierte Authentifizierung mit sicheren Keys erlauben, ...

Dass alle Datenbanken im Klartext-Format im Repository abgelegt werden, hat in erster Linie einen technischen Grund: Git kann mit Änderungen von Binärdaten (wie die Datenbank-Dateien) nicht gut umgehen - das Repository würde nach einigen Monaten oder Jahren der Nutzung mehrere GB in Anspruch nehmen, die Synchronisation wäre entsprechend langsam.

Der Export als Klartext hat zudem den Vorteil, dass Änderungen an den Datenbanken einfacher nachvollziehbar sind. Dadurch, dass bei jedem Start die Datenbanken neu angelegt werden, werden dadurch [Updates der Datenbank auf die aktuelle Datenbank-Engine](https://jverein-forum.de/viewtopic.php?t=4525) automatisch durchgeführt.

### Kann ich die Versionskontrolle auch ohne online verfügbares Git-Repository verwenden?

Ja. Dazu kann ein weiteres Repository auf der Festplatte angelegt werden, das dann als Pseudo-Online-Repository dient. [TODO]

### Läuft jverein-multiuser unter Windows/macOS/Linux?

Ja.

### Wie funktioniert das Sperren für andere Nutzer (Lock-File)?

Beim Start aktualisiert jverein-multiuser das Git-Repository (git pull) und prüft, ob es ein [Tag](https://git-scm.com/book/en/v2/Git-Basics-Tagging) gibt, das mit "lock" anfängt. Sollte solch ein Tag existieren, verweigert das Script den Start von jVerein und gibt den Namen des Tags aus (dieser enthält u. A. den Namen der Person, die das Tag angelegt hat). Sollte beim Start kein solches Tag existieren, wird ein neues angelegt und ins Online-Repository hochgeladen. Dann wird jVerein gestartet.

Nach dem Beenden von jVerein, der Eingabe einer Commit-Message und dem pushen des aktuellen Standes ins Online-Repository wird das Tag wieder entfernt.

Dadurch, dass das Aktualisieren des Repositories und das Anlegen und Hochladen des Tags einzelne Operationen sind alle etwas Zeit in Anspruch nehmen, gibt es eine Race Condition: Wenn zwei Nutzer exakt zur gleichen Zeit das Lock anfordern, wird jVerein bei beiden Nutzern gestartet. Dieses Szenario ist allerdings so unwahrscheinlich, dass es für diese Zwecke akzeptabel ist. Selbst wenn es eintritt, stellt Git beim Hochladen eine Kollision fest. Ein Nutzer muss dann ggf. seine Änderungen verwerfen.

### Gibt es Alternativen?

Ja, es gibt diverse alternative Ansätze, Multiuser-Fähigkeit für jVerein umzusetzen. Diese sind in der jVerein-Dokumentation beschrieben: https://doku.jverein.de/allgemein/multiuser



## Installation

### Voraussetzungen

* [Standardinstallation](https://doku.jverein.de/allgemein/installation) von Jameica, Hibiscus und jVerein mit mindestens Jameica 2.6.3, ggf. per [Jameica-Mashup](https://hibiscus-mashup.derrichter.de/)
  * Datenbank: H2 (Standard), nicht MySQL
* Python 3.8+



## Known Issues

### SSH

* reduce key password requests by using ssh-agent

https://help.github.com/en/github/authenticating-to-github/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent#adding-your-ssh-key-to-the-ssh-agent

### Ändern des Master-Passworts

