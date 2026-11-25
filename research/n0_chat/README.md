# Neuravale N0 Chat 003

Original randomly initialized two-layer causal transformer. 102,871 parameters, 215-token vocabulary, 1,608 synthetic dialogue examples. No third-party pretrained weights. The local run achieved 25/41 exact matches on a development suite reused during iteration. Not a general-purpose assistant.

## Checkpoint status

The exact locally trained checkpoint and complete archive have NOT been uploaded yet. See local_run_summary.json for the SHA-256 hashes and measured results. To import the original archive, extract its contents into this directory and verify the checkpoint hash.

## Reproduction

Install Python 3.11+ and PyTorch 2.10, then run `python research/n0_chat/train.py`. This generates the vocabulary, training and test datasets, report, and a fresh checkpoint. Reproduced weights may differ across environments. Run `python research/n0_chat/chat.py` to chat locally. Type /reset or /quit.

This research model is not connected to the public web chat. The repository is public; publishing weights here makes them publicly accessible. No model license grant is implied by this note.
