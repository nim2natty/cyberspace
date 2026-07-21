"""robodaddy - plan and dispatch small LLM fine-tunes.

Pick a model use case, review public Hugging Face dataset recommendations,
choose a base model and GPU class, then dry-run locally or dispatch a QLoRA
training job to a Vast.ai instance. Completed local records can be served through
an Ollama-compatible endpoint and configured as cyberspace's custom provider.

  datasets   browse public training-data recommendations for a request
  usecases   see use-case presets -> recommended data + model + GPU
  providers  list GPU-rental marketplaces
  instances  search live GPU offers on Vast.ai
  build      guided intent -> live data -> GPU/price -> confirmed background training
  plan       advanced interactive planning without launch
  train      launch one or more detached jobs (or --foreground)
  dashboard  watch concurrent queued/training/done/failed jobs
  models     registry of trained models
  serve      write a local Ollama Modelfile and issue a local API key record
  keys       securely create/show/list/revoke served-model keys
  connect    set a trained+served model as cyberbot's active LLM

For LEGAL, authorized use. Training uses public datasets under their own licenses;
respect each dataset's terms. Cloud GPU rental costs real money - every command
that would spend shows the cost first and asks before proceeding.
"""
__version__ = "0.7.0"
