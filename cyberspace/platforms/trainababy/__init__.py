"""trainababy - train your own personalized AI model, end to end.

Pick a use case (offensive pentest, defensive, personal assistant, ...), choose a
public training dataset + base model + GPU, train for N days on rented cloud GPUs
(Vast.ai etc.), then serve the finished model behind an OpenAI-compatible API key
you can plug back into cyberbot as its brain. This is "TrainABaby".

  datasets   browse the public training-data catalog (by use case)
  usecases   see use-case presets -> recommended data + model + GPU
  providers  list GPU-rental marketplaces
  instances  search live GPU offers on Vast.ai (needs VAST_API_KEY)
  plan       interactive: usecase -> data -> GPU -> days -> cost estimate
  train      generate + launch the fine-tune job (real if configured, dry-run else)
  jobs       list training jobs + statistics (loss, samples, $, days)
  models     registry of trained models
  serve      deploy a trained model behind an OpenAI-compatible endpoint + key
  keys       manage API keys for served models
  use        set a trained+served model as cyberbot's active LLM

For LEGAL, authorized use. Training uses public datasets under their own licenses;
respect each dataset's terms. Cloud GPU rental costs real money - every command
that would spend shows the cost first and asks before proceeding.
"""
__version__ = "0.1.0"
