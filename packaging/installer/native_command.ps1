# Shared native-command invocation for the PoseCap installer handlers (task 0028).

#Requires -Version 5.1

function Invoke-NativeCommand {
    # Windows PowerShell 5.1 wraps every redirected stderr line of a native
    # command in an ErrorRecord; under the handlers' $ErrorActionPreference =
    # "Stop" the first such line becomes a terminating error before the exit
    # code is ever checked. Preference variables are dynamically scoped, so
    # relaxing the preference here confines the relaxation to this call and
    # restores "Stop" on return or throw. Callers decide success from
    # $LASTEXITCODE and the returned lines only; stderr text stays merged in
    # the output so it still reaches the bootstrap transcript log.
    param(
        [Parameter(Mandatory = $true)] [string]$FilePath,
        [string[]]$ArgumentList = @()
    )
    $ErrorActionPreference = "Continue"
    & $FilePath @ArgumentList 2>&1 | ForEach-Object { "$_" }
}
