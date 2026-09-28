@echo off
REM ===========================================================================
REM Relais local de la veille : collecte les sites injoignables depuis
REM l'hebergeur (portail officiel marchespublics.sn, qui n'accepte que les
REM connexions venant du Senegal) et les depose sur app.adoc-consulting.com.
REM
REM A programmer une fois par jour dans le Planificateur de taches Windows.
REM Le jeton se met dans app\backend\.ingest_token (meme valeur que la
REM variable INGEST_TOKEN configuree sur Railway).
REM ===========================================================================
cd /d "%~dp0app\backend"
venv\Scripts\python.exe collect_local.py
