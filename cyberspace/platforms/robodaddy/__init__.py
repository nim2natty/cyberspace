"""robodaddy - plan and dispatch small LLM fine-tunes.

Pick a model use case, review public Hugging Face dataset recommendations,
choose a base model and GPU class, then dry-run locally or dispatch a QLoRA
training job to a Vast.ai instance. Completed local records can be served through
an Ollama-compatible endpoint and configured as cyberspace's custom provider.

  datasets   browse public training-data recommendations for a request
  usecases   see use-case presets -> recommended data + model + GPU
  providers  list GPU-rental marketplaces
  instances  search live GPU offers on Vast.ai
  plan       interactive: usecase -> data -> GPU -> days -> cost estimate
  train      generate one or more training jobs (dry-run or Vast.ai dispatch)
  jobs       list training jobs + statistics (loss, samples, $, days)
  models     registry of trained models
  serve      write a local Ollama Modelfile and issue a local API key record
  keys       manage API keys for served models
  use        set a trained+served model as cyberbot's active LLM

For LEGAL, authorized use. Training uses public datasets under their own licenses;
respect each dataset's terms. Cloud GPU rental costs real money - every command
that would spend shows the cost first and asks before proceeding.
"""
__version__ = "0.1.0"
