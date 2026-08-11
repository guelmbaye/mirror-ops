<#
.SYNOPSIS
    Taches MIRROR OPS pour Windows / PowerShell.

.DESCRIPTION
    Le Makefile ne sert a rien sous Windows sans outillage supplementaire.
    Ce script couvre les memes taches et trouve tout seul l'interpreteur du
    venv (apps\api\.venv), pour qu'aucune commande ne depende du repertoire
    courant ni d'une activation prealable.

.EXAMPLE
    .\scripts\mirror-ops.ps1 help
    .\scripts\mirror-ops.ps1 dev-api
    .\scripts\mirror-ops.ps1 garments
    .\scripts\mirror-ops.ps1 import-garments -Path $HOME\Downloads\vetements -DryRun
    .\scripts\mirror-ops.ps1 import-garments -Path $HOME\Downloads\vetements

    Les commutateurs sont PowerShell (-DryRun, -Auto), pas POSIX (--dry-run).
    .\scripts\mirror-ops.ps1 probe -Photo .\ma-photo.jpg -Garment jacket_01
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet(
        'help', 'install', 'dev-api', 'dev-web', 'build', 'test', 'test-api', 'test-web', 'audit',
        'demo', 'calibrate', 'openapi', 'schema', 'garments', 'import-garments', 'probe',
        'health', 'clean'
    )]
    [string]$Task = 'help',

    # import-garments : dossier de photos, ou fichier unique avec -Id
    [string]$Path,
    [string]$Id,

    # probe : photo de la personne et vetement (identifiant ou chemin)
    [string]$Photo,
    [string]$Garment,

    [switch]$DryRun,

    # import-garments : attribuer aussi les photos non reconnues
    [switch]$Auto
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root 'apps\api'

function Get-Python {
    # Priorite au venv du projet : c'est lui qui porte les dependances.
    $venv = Join-Path $ApiDir '.venv\Scripts\python.exe'
    if (Test-Path $venv) { return $venv }

    foreach ($candidate in 'python', 'python3', 'py') {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    throw "Python introuvable. Creez le venv : python -m venv apps\api\.venv"
}

function Invoke-Py {
    param([string[]]$Arguments, [string]$WorkingDirectory = $Root)

    Push-Location $WorkingDirectory
    try { & (Get-Python) @Arguments }
    finally { Pop-Location }
}

function Show-Help {
    Write-Host ""
    Write-Host "MIRROR OPS - taches disponibles" -ForegroundColor Cyan
    Write-Host ""
    $rows = [ordered]@{
        'install'         = 'Installer backend + frontend'
        'dev-api'         = 'Lancer l''API           http://localhost:8000'
        'dev-web'         = 'Lancer l''interface     http://localhost:3000'
        'build'           = 'Compiler le frontend en production'
        'test'            = 'Tests backend + frontend'
        'audit'           = 'Verifier le parcours de bout en bout, champ par champ'
        'demo'            = 'Derouler le parcours complet contre l''API locale'
        'calibrate'       = 'Classement des candidats ONE CHANGE'
        'openapi'         = 'Exporter docs\openapi.json'
        'schema'          = 'Colonnes manquantes dans la base'
        'garments'        = 'Le catalogue contient-il de vraies photos ?'
        'import-garments' = 'Importer des photos : -Path <dossier> [-DryRun] [-Auto]'
        'probe'           = 'Un seul essayage YouCam : -Photo <fichier> -Garment <id>'
        'health'          = 'Etat des dependances de l''API'
        'clean'           = 'Supprimer caches et artefacts'
    }
    foreach ($key in $rows.Keys) {
        Write-Host ("  {0,-17} {1}" -f $key, $rows[$key])
    }
    Write-Host ""
}

switch ($Task) {
    'help' { Show-Help }

    'install' {
        Invoke-Py @('-m', 'pip', 'install', '-r', 'requirements-dev.txt') $ApiDir
        Push-Location $Root; try { npm install } finally { Pop-Location }
    }

    'dev-api' {
        Invoke-Py @('-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000') $ApiDir
    }

    'dev-web'   { Push-Location $Root; try { npm run dev } finally { Pop-Location } }
    'build'     { Push-Location $Root; try { npm run build } finally { Pop-Location } }
    'test-api'  { Invoke-Py @('-m', 'pytest', '-q') $ApiDir }
    'test-web'  { Push-Location $Root; try { npm run test --workspace '@mirror-ops/web' } finally { Pop-Location } }

    'test' {
        Invoke-Py @('-m', 'pytest', '-q') $ApiDir
        Push-Location $Root; try { npm run test --workspace '@mirror-ops/web' } finally { Pop-Location }
    }

    'audit' {
        # Verifier d'abord que l'API repond : sinon l'audit ne peut rien dire
        # d'utile, et un code d'erreur reseau n'aide personne.
        try {
            Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 3 | Out-Null
        }
        catch {
            Write-Host "L'API ne repond pas sur http://localhost:8000" -ForegroundColor Yellow
            Write-Host "Lancez-la dans un autre terminal :  .\scripts\mirror-ops.ps1 dev-api"
            break
        }
        Invoke-Py @('scripts\audit_journey.py')
    }
    'demo'      { Invoke-Py @('scripts\demo_flow.py') }
    'calibrate' { Invoke-Py @('scripts\calibrate_engine.py') }
    'openapi'   { Invoke-Py @('scripts\export_openapi.py') }
    'garments'  { Invoke-Py @('scripts\check_garments.py') }

    'schema' {
        $arguments = @('scripts\sync_schema.py')
        if ($DryRun) { $arguments += '--dry-run' }
        Invoke-Py $arguments
    }

    'import-garments' {
        if (-not $Path) { throw "Indiquez -Path <dossier> (ou -Path <fichier> -Id jacket_01)" }
        # Resolution explicite : un chemin relatif ou « ~ » ne survit pas
        # toujours au passage vers un executable natif.
        $resolved = (Resolve-Path -LiteralPath $Path).Path
        $arguments = @('scripts\import_garments.py', $resolved)
        if ($Id)     { $arguments += @('--id', $Id) }
        if ($Auto)   { $arguments += '--auto' }
        if ($DryRun) { $arguments += '--dry-run' }
        Invoke-Py $arguments
    }

    'probe' {
        if (-not $Photo -or -not $Garment) {
            throw "Indiquez -Photo <fichier> et -Garment <identifiant ou chemin>"
        }
        $resolvedPhoto = (Resolve-Path -LiteralPath $Photo).Path
        Invoke-Py @('scripts\probe_vto.py', $resolvedPhoto, $Garment)
    }

    'health' {
        try {
            Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/health/dependencies' |
                Format-List
        }
        catch {
            Write-Host "L'API ne repond pas sur :8000. Lancez d'abord : .\scripts\mirror-ops.ps1 dev-api" -ForegroundColor Yellow
        }
    }

    'clean' {
        Get-ChildItem -Path $Root -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        foreach ($item in @('apps\api\.pytest_cache', 'apps\api\var', 'apps\web\.next',
                            'apps\web\tsconfig.tsbuildinfo')) {
            $full = Join-Path $Root $item
            if (Test-Path $full) { Remove-Item -Recurse -Force $full }
        }
        Write-Host "Nettoye." -ForegroundColor Green
    }
}
