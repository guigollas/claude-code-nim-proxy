# Claude Code Nim Proxy

A LiteLLM-based proxy that routes Claude Code model requests through NVIDIA NIM API, enabling the use of alternative models (GLM, DeepSeek, Qwen) while maintaining compatibility with Claude Code's model aliases.

## Overview

This proxy intercepts Claude Code's API calls and transparently maps model aliases to NVIDIA NIM endpoints:

| Claude Alias | Actual Model | Provider |
|-------------|--------------|----------|
| `sonnet` | `z-ai/glm-5.1` | NVIDIA NIM |
| `fable` | `deepseek-ai/deepseek-v4-pro` | NVIDIA NIM |
| `opus` | `qwen/qwen3.5-397b-a17b` | NVIDIA NIM |
| `haiku` | `deepseek-ai/deepseek-v4-flash` | NVIDIA NIM |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Claude Code │ ──► │ LiteLLM      │ ──► │ NVIDIA NIM API  │
│  (cli/app)  │     │ Proxy:4000   │     │ (integrate.api) │
└─────────────┘     └──────────────┘     └─────────────────┘
                          │
                     Model Mapping:
                     sonnet → glm-5.1
                     fable  → deepseek-v4-pro
                     opus   → qwen3.5-397b
                     haiku  → deepseek-v4-flash
```

## Prerequisites

- Python 3.12+
- pip and venv
- NVIDIA NIM API key (get from https://build.nvidia.com/)

## Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url> claude-code-nim-proxy
cd claude-code-nim-proxy
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install litellm
```

### 3. Set Up Environment Files

Create the configuration directory:

```bash
mkdir -p ~/.config/nim-proxy
```

Create the API key file at `~/.config/nim-proxy/nvidia.env`:

```bash
export NVIDIA_NIM_API_KEY="nvapi-your-actual-key-here"
export NVIDIA_API_KEY="$NVIDIA_NIM_API_KEY"
```

> **Security Note:** Never commit the `nvidia.env` file to version control. This project includes it in `.gitignore`.

### 4. Create Claude Environment File

Create `~/.claude-code-nim.env` in your home directory:

```bash
export ANTHROPIC_BASE_URL="http://localhost:4000"
export ANTHROPIC_AUTH_TOKEN="sk-local-jarvis"
export ANTHROPIC_MODEL="sonnet"

# Optional: Model name labels for display
export ANTHROPIC_DEFAULT_SONNET_MODEL="sonnet"
export ANTHROPIC_DEFAULT_FABLE_MODEL="fable"
export ANTHROPIC_DEFAULT_OPUS_MODEL="opus"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="haiku"

export ANTHROPIC_DEFAULT_SONNET_MODEL_NAME="GLM 5.1 via NVIDIA NIM"
export ANTHROPIC_DEFAULT_FABLE_MODEL_NAME="DeepSeek V4 Pro via NVIDIA NIM"
export ANTHROPIC_DEFAULT_OPUS_MODEL_NAME="Qwen 3.5 397B via NVIDIA NIM"
export ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME="DeepSeek V4 Flash via NVIDIA NIM"
```

### 5. Install Scripts

Copy the proxy scripts to your local bin:

```bash
mkdir -p ~/.local/bin
cp nim-proxy ~/.local/bin/
cp claude-nim ~/.local/bin/
chmod +x ~/.local/bin/nim-proxy ~/.local/bin/claude-nim
```

Ensure `~/.local/bin` is in your PATH by adding this to your `~/.bashrc` or `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### 6. Update Configuration Paths

Edit `nim-proxy` script and update the `PROXY_DIR` variable to point to your clone location:

```bash
PROXY_DIR="/absolute/path/to/claude-code-nim-proxy"
```

## Usage

### Starting the Proxy

Run the proxy in a terminal:

```bash
nim-proxy
```

You should see:

```
Iniciando LiteLLM/NVIDIA proxy...
Config: /path/to/nim_config.yaml
Porta: http://localhost:4000
Credencial NVIDIA_NIM_API_KEY carregada.
```

Keep this terminal open – the proxy runs in the foreground.

### Using Claude Code

In a **new terminal** (with the proxy running), source the environment and start Claude:

```bash
source ~/.claude-code-nim.env
claude
```

Or simply run:

```bash
claude-nim
```

### Testing Model Switching

Inside Claude Code, use the `/model` command:

```
/model sonnet   # Uses GLM 5.1
/model fable    # Uses DeepSeek V4 Pro
/model opus     # Uses Qwen 3.5 397B
/model haiku    # Uses DeepSeek V4 Flash
```

## Configuration Reference

### nim_config.yaml

The LiteLLM configuration file defines model mappings:

```yaml
model_list:
  - model_name: sonnet          # Alias Claude Code uses
    litellm_params:
      model: nvidia_nim/z-ai/glm-5.1   # Actual NVIDIA model
      api_key: os.environ/NVIDIA_NIM_API_KEY
      api_base: https://integrate.api.nvidia.com/v1

litellm_settings:
  drop_params: true            # Remove unsupported params
  set_verbose: false           # Enable for debugging

general_settings:
  master_key: sk-local-jarvis  # Auth token for proxy
```

### Environment Variables

| Variable | Location | Purpose |
|----------|----------|---------|
| `NVIDIA_NIM_API_KEY` | `~/.config/nim-proxy/nvidia.env` | API key for NVIDIA NIM |
| `ANTHROPIC_BASE_URL` | `~/.claude-code-nim.env` | Points Claude to local proxy |
| `ANTHROPIC_AUTH_TOKEN` | `~/.claude-code-nim.env` | Auth token (must match `master_key`) |
| `ANTHROPIC_MODEL` | `~/.claude-code-nim.env` | Default model alias |

## Troubleshooting

### "NVIDIA_NIM_API_KEY not defined"

Ensure `~/.config/nim-proxy/nvidia.env` exists and contains:

```bash
export NVIDIA_NIM_API_KEY="nvapi-your-key"
```

### "LiteLLM not found"

Verify the virtual environment:

```bash
ls -la /path/to/claude-code-nim-proxy/.venv/bin/litellm
```

If missing, reinstall:

```bash
source .venv/bin/activate
pip install litellm
```

### Connection Refused

Make sure the proxy is running **before** starting Claude Code. The proxy must stay running in the background.

### Model Not Switching

Check that:
1. `nim_config.yaml` has the model alias defined
2. The proxy logs show successful startup
3. `ANTHROPIC_BASE_URL` is set to `http://localhost:4000`

## Security Considerations

- **Never commit API keys**: The `nvidia.env` file is in `.gitignore`
- **Local-only binding**: Proxy runs on `localhost:4000` – not exposed externally
- **Auth token**: Change `master_key` in `nim_config.yaml` and `ANTHROPIC_AUTH_TOKEN` if deploying in a shared environment

## License

MIT

## Author

Generated for claude-code-nim-proxy deployment.