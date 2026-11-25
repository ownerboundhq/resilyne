# Neuravale N1 Lite — SFT 001

Experimental supervised fine-tune of [SmolLM2-135M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct) (Apache-2.0), using LoRA on the query and value projections. The 32 original synthetic training examples target assistant identity, concise answers and uncertainty; eight separate validation examples measure held-out answer loss. Four held-out prompts are also generated before and after training. This is a pipeline proof, not a broad capability benchmark. No customer data is used.

GitHub Actions runs the experiment on a bounded CPU runner and uploads the adapter plus report as a build artifact. The output contains a new adapter only, not a standalone foundation model. The upstream revision and dataset hashes are recorded. Review the report and expand evaluation before merging or deploying the adapter. Preserve upstream license and attribution when redistributing.

Local: install CPU PyTorch 2.5.1 and the pinned requirements, then run `python research/n1_lite/train.py`. A CUDA device is optional. To reproduce a run, use the recorded revision and seed.
