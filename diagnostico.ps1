# Quien es el proveedor sin razon social. SOLO LECTURA.
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "diagnostico-ultima-corrida.txt") -Force | Out-Null } catch { }
$b64 = @"
LS0gwr9RdWnDqW4gZXMgZWwgcHJvdmVlZG9yIHNpbiByYXrDs24gc29jaWFsIGRlbCBQYW5lbD8gKHByZWd1bnRhIGRlIEd1aWxsZXJtbykKLS0KLS0gU09M
TyBMRUNUVVJBLiBEb3MgcHJlZ3VudGFzLCB5IGxhIHNlZ3VuZGEgZXMgbGEgcXVlIGltcG9ydGE6Ci0tICAgMS4gwr9RdcOpIGRpY2UgZWwgY29udHJhdG8/
Ci0tICAgMi4gwr9MYSByYXrDs24gc29jaWFsIHZpZW5lIHZhY8OtYSBERSBMQSBGVUVOVEUsIG8gbGEgcGVyZGltb3Mgbm9zb3Ryb3MgYWwKLS0gICAgICBu
b3JtYWxpemFyPyBDdWxwYXIgYSBsYSBmdWVudGUgc2luIGNvbXByb2JhcmxvIGVzIGxhIGZvcm1hIG3DoXMgY8OzbW9kYQotLSAgICAgIGRlIG5vIGVuY29u
dHJhciB1biBmYWxsbyBwcm9waW8uCgpccHNldCBib3JkZXIgMgpccHNldCBudW1lcmljbG9jYWxlIG9uCgotLSAxLiBFbCBjb250cmF0bywgdGFsIGNvbW8g
cXVlZMOzIG5vcm1hbGl6YWRvLgpTRUxFQ1QgaWRfY29udHJhdG8sIHByb3ZlZWRvcl90aXBvLCBwcm92ZWVkb3JfbnVtZXJvLCBwcm92ZWVkb3Jfbm9tYnJl
LAogICAgICAgbGVmdChub21icmVfZW50aWRhZCwgNDQpIEFTIGVudGlkYWQsIG5pdF9lbnRpZGFkLAogICAgICAgdmFsb3I6Om51bWVyaWMoMjAsMCksIGVz
dGFkbywgZmVjaGFfZGVfZmlybWEsCiAgICAgICBkZXBhcnRhbWVudG9fbm9tYnJlLCBvcmRlbgpGUk9NIGNvbnRyYXRvCldIRVJFIHByb3ZlZWRvcl9udW1l
cm8gPSAnOTAwNDQ1NzM2JzsKCi0tIDIuIExPIFFVRSBESUpPIExBIEZVRU5URSwgc2luIHBhc2FyIHBvciBudWVzdHJvIGPDs2RpZ28uClNFTEVDVCBjb250
ZW5pZG8tPj4ncHJvdmVlZG9yX2FkanVkaWNhZG8nICAgQVMgcmF6b25fc29jaWFsX2VuX2xhX2Z1ZW50ZSwKICAgICAgIGNvbnRlbmlkby0+Pidkb2N1bWVu
dG9fcHJvdmVlZG9yJyAgICBBUyBkb2N1bWVudG8sCiAgICAgICBjb250ZW5pZG8tPj4ndGlwb2RvY3Byb3ZlZWRvcicgICAgICAgQVMgdGlwb19kb2MsCiAg
ICAgICBjb250ZW5pZG8tPj4nZXNfZ3J1cG8nICAgICAgICAgICAgICAgQVMgZXNfZ3J1cG8sCiAgICAgICBjb250ZW5pZG8tPj4nZXN0YWRvX2NvbnRyYXRv
JyAgICAgICAgQVMgZXN0YWRvLAogICAgICAgY29udGVuaWRvLT4+J25vbWJyZV9yZXByZXNlbnRhbnRlX2xlZ2FsJyBBUyByZXByZXNlbnRhbnRlLAogICAg
ICAgY29udGVuaWRvLT4+J2Rlc2NyaXBjaW9uX2RlbF9wcm9jZXNvJyAgICBBUyBvYmpldG8sCiAgICAgICBjb250ZW5pZG8tPid1cmxwcm9jZXNvJy0+Pid1
cmwnICAgICAgQVMgZW5sYWNlX3NlY29wCkZST00gY3J1ZG9fcmVnaXN0cm8KV0hFUkUgZGF0YXNldCA9ICdjb250cmF0b3MnCiAgQU5EIGNvbnRlbmlkby0+
Pidkb2N1bWVudG9fcHJvdmVlZG9yJyA9ICc5MDA0NDU3MzYnCk9SREVSIEJZIGNvbnN1bHRhZG9fZW4gREVTQwpMSU1JVCAzOwoKLS0gMy4gwr9FcyB1biBj
YXNvIGFpc2xhZG8gbyB1biBwYXRyw7NuPyBDdcOhbnRvcyBjb250cmF0b3MgdHJhZW4gZG9jdW1lbnRvCi0tICAgIHV0aWxpemFibGUgWSByYXrDs24gc29j
aWFsIGNlbnRpbmVsYSwgeSBjdcOhbnRhIHBsYXRhIG11ZXZlbi4KU0VMRUNUIGNvdW50KCopIEFTIGNvbnRyYXRvcywKICAgICAgIHN1bSh2YWxvcik6Om51
bWVyaWMoMjAsMCkgQVMgdmFsb3IsCiAgICAgICBjb3VudChESVNUSU5DVCBwcm92ZWVkb3JfbnVtZXJvKSBBUyBkb2N1bWVudG9zX2Rpc3RpbnRvcwpGUk9N
IGNvbnRyYXRvCldIRVJFIHByb3ZlZWRvcl90aXBvIElTIE5PVCBOVUxMCiAgQU5EIHVwcGVyKGNvYWxlc2NlKHByb3ZlZWRvcl9ub21icmUsJycpKSBJTgog
ICAgICAoJ05PIERFRklOSURPJywnU0lOIERFU0NSSVBDSU9OJywnTk8gREVGSU5JREEnLCdOTyBBUExJQ0EnLCcnKTsKCi0tIDQuIExvcyBkaWV6IG1heW9y
ZXMgZGUgZXNlIHBhdHLDs246IHNvbiBwcm92ZWVkb3JlcyBpZGVudGlmaWNhYmxlcyBwb3IKLS0gICAgZG9jdW1lbnRvIGEgbG9zIHF1ZSBsYSBlbnRpZGFk
IG5vIGxlcyBlc2NyaWJpw7MgZWwgbm9tYnJlLgpTRUxFQ1QgcHJvdmVlZG9yX251bWVybywgbGVmdChub21icmVfZW50aWRhZCwgNDYpIEFTIGVudGlkYWQs
CiAgICAgICB2YWxvcjo6bnVtZXJpYygyMCwwKSwgZXN0YWRvLCBmZWNoYV9kZV9maXJtYQpGUk9NIGNvbnRyYXRvCldIRVJFIHByb3ZlZWRvcl90aXBvIElT
IE5PVCBOVUxMCiAgQU5EIHVwcGVyKGNvYWxlc2NlKHByb3ZlZWRvcl9ub21icmUsJycpKSBJTgogICAgICAoJ05PIERFRklOSURPJywnU0lOIERFU0NSSVBD
SU9OJywnTk8gREVGSU5JREEnLCdOTyBBUExJQ0EnLCcnKQpPUkRFUiBCWSB2YWxvciBERVNDIE5VTExTIExBU1QKTElNSVQgMTA7Cg==
"@
[IO.File]::WriteAllBytes((Join-Path $raiz "diagnostico-proveedor.sql"), [Convert]::FromBase64String(($b64 -replace '\s','')))
function Buscar($n) {
    $p = Get-Command $n -ErrorAction SilentlyContinue
    if ($p) { return $p.Source }
    foreach ($r in @("C:\Program Files\PostgreSQL","C:\Program Files (x86)\PostgreSQL")) {
        if (-not (Test-Path $r)) { continue }
        foreach ($v in (Get-ChildItem $r -Directory -EA SilentlyContinue |
            Sort-Object { if ($_.Name -match '^(\d+)') { [int]$Matches[1] } else { 0 } } -Descending)) {
            $ruta = Join-Path $v.FullName "bin\$n.exe"
            if (Test-Path $ruta) { return $ruta }
        }
    }
    return $null
}
$PSQL = Buscar "psql"
if (-not $PSQL) { Write-Host "No encuentro psql." -ForegroundColor Red; Read-Host "Enter"; exit 1 }
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"
$antes = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $PSQL -h localhost -U vigia -d vigia -f "diagnostico-proveedor.sql" 2>&1 | Out-Host
$ErrorActionPreference = $antes
try { Stop-Transcript | Out-Null } catch { }
