param(
    [string]$Model = $env:OLLAMA_MODEL,
    [string]$BaseUrl = $env:OLLAMA_BASE_URL,
    [int]$TimeoutSeconds = 20
)

if ([string]::IsNullOrWhiteSpace($Model)) {
    $Model = "qwen2.5:1b"
}

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = "http://127.0.0.1:11434"
}

$Uri = "{0}/api/chat" -f $BaseUrl.TrimEnd('/')
$messages = @()

Write-Host "Rival Ollama Chat | model=$Model | endpoint=$Uri" -ForegroundColor Cyan
Write-Host "Type 'exit' or 'quit' to stop." -ForegroundColor DarkGray

while ($true) {
    Write-Host "" 
    $userInput = Read-Host "You"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        continue
    }

    if ($userInput.ToLowerInvariant() -in @("exit", "quit")) {
        break
    }

    $messages += @{ role = "user"; content = $userInput }

    $payloadObject = @{
        model = $Model
        stream = $true
        messages = $messages
    }

    $payload = $payloadObject | ConvertTo-Json -Depth 6

    Write-Host "Rival> " -NoNewline -ForegroundColor Green
    $assistantResponse = ""

    try {
        $request = [System.Net.HttpWebRequest]::Create($Uri)
        $request.Method = "POST"
        $request.ContentType = "application/json"
        $request.Timeout = $TimeoutSeconds * 1000

        $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
        $requestStream = $request.GetRequestStream()
        $requestStream.Write($bytes, 0, $bytes.Length)
        $requestStream.Close()

        $response = $request.GetResponse()
        $stream = $response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)

        while (-not $reader.EndOfStream) {
            $line = $reader.ReadLine()
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }

            $chunk = $line | ConvertFrom-Json
            $textChunk = $chunk.message.content
            if (-not [string]::IsNullOrEmpty($textChunk)) {
                Write-Host $textChunk -NoNewline
                $assistantResponse += $textChunk
            }
        }

        $reader.Close()
        $response.Close()
        Write-Host ""
    }
    catch {
        Write-Host "`nError connecting to Ollama: $_" -ForegroundColor Red
        continue
    }

    if (-not [string]::IsNullOrWhiteSpace($assistantResponse)) {
        $messages += @{ role = "assistant"; content = $assistantResponse }
    }
}
