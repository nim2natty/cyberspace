"""robodaddy - design and train your own open source model.

RoboDaddy lets you design a model with a full set of parameters and then fine-tune
an open-weights base on a dataset you pick. You can browse Hugging Face data
(curated catalog + live discovery) and enter a Hugging Face dataset repo id, set your own
training parameters (or use the built-in profiles), set the guardrails that are
applied before the model is used, dispatch a QLoRA training job to a Vast.ai
instance, then serve the finished model through an Ollama-compatible endpoint and
configure it as cyberspace's custom provider.

Build a CYBER BOT (authorized red-team / adversary emulation or defense) or a
custom BOT with user-defined supported parameters.
limited. The cyber profile attunes training to full offensive reasoning,
realistic adversary modeling, and attack-path reasoning: analyze footholds,
explore exploitability, chain findings, and reason through full multi-step attack
paths, grounded in real attack vectors and operator-inspired, multi-turn
scenarios. Guardrails you set before deployment keep the resulting open source
model scoped for authorized use, so the same reasoning supports autonomous
red-team operations and deep defensive workflows with accuracy.

  datasets   browse public training-data recommendations + register any HF dataset
  latest     view the most recent Hugging Face datasets cached by the last refresh
  start      guided, AI-assisted build (refresh latest data -> cyber/custom ->
             AI-recommended parameters -> your system prompt -> AI enhancement ->
             GPU time/cost table with an auto best-pick) -- the recommended entry point
  parameters view/set/reset the full model-design parameters (hyperparameters,
             cyber focus, guardrails) and get a built-in guide
  cyber      build a cyber bot (red-team/adversary emulation or defense)
  custom     build a custom bot with user-defined supported parameters
  usecases   see use-case presets -> recommended data + model + GPU
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
__version__ = "0.8.0"
