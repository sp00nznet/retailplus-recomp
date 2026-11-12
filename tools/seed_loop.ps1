# Bring-up loop: run the harness on the recomp, seed what it could not
# dispatch, lift just those (run_lift.py --add) and rebuild, until a run
# finds nothing new. -Rounds caps it.
param([int]$Rounds = 5)
$Root = Split-Path -Parent $PSScriptRoot
if (-not $env:PCRECOMP) { $env:PCRECOMP = Join-Path (Split-Path -Parent $Root) 'pcrecomp' }
$env:CMAKE_ARGS = "-DPCRECOMP=$($env:PCRECOMP -replace '\\', '/')"
for ($i = 1; $i -le $Rounds; $i++) {
  $out = & py -3 (Join-Path $Root 'tools\pos_diff.py') --only recomp 2>&1 | Out-String
  $log = (Get-ChildItem $env:TEMP -Directory -Filter rp_recomp_* | Sort-Object LastWriteTime -Descending)[0].FullName + '\recomp.log'
  $seeds = & py -3 (Join-Path $Root 'tools\seeds_from_log.py') $log
  Write-Host "round $i`: $seeds"
  if ($seeds -match '^0 new') { Write-Host $out; break }
  Push-Location $Root
  & py -3 run_lift.py --add | Select-Object -Last 3
  cmd /c "`"$Root\build.cmd`"" | Select-Object -Last 1
  Pop-Location
}
