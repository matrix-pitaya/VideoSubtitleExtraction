$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$sampleFolder = Join-Path $PSScriptRoot '..\public\samples'
New-Item -ItemType Directory -Path $sampleFolder -Force | Out-Null
$sampleFolder = (Resolve-Path -LiteralPath $sampleFolder).Path
$sampleVoice = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $sampleVoice.SelectVoice('Microsoft Huihui Desktop')
    $sampleFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $sampleVoice.SetOutputToWaveFile((Join-Path $sampleFolder 'chinese.wav'), $sampleFormat)
    $sampleVoice.Speak((Get-Content -LiteralPath (Join-Path $sampleFolder 'reference.txt') -Encoding UTF8 -Raw))
} finally { $sampleVoice.Dispose() }
