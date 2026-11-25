# Arc Next: one billion pretraining token positions

**Status: configured, not trained to this target.** Starting point: verified alignment checkpoint, 5,000,192 pretraining positions + 616,338 assistant positions, 4,240,896 parameters, 0/60 strict evaluation. Training target: cumulative 1,000,000,000 pretraining positions, then another 1,000,000 supervised assistant positions. The final batch may exceed its target slightly. Processed positions are not unique documents or necessarily unique text.

This is a dedicated-compute campaign, not a GitHub Actions training job. Repeating the original 11.54M-position corpus roughly 86 times would be a poor substitute for expanding the dataset. The expanded corpus uses the original pinned Cosmopedia source and tokenizer; it exact-deduplicates cleaned text, excludes original documents and the hash-based held-out partition, records provenance and checksums, and refuses to train with fewer than 250M new corpus positions. It does not guarantee semantic deduplication or complete rights, accuracy, privacy and safety review. Cosmopedia is synthetic text; no external model weights are loaded. The existing human-dialogue corpus is used for the final alignment stage, whose repeated exposure may overfit.

## Run on dedicated GPU

Obtain the original checkpoint and tokenizer from [the verified alignment artifact](https://github.com/ownerboundhq/resilyne/actions/runs/45536827037/artifacts/14987815657), extract into `research/arc_next` (preserving run/checkpoint.pt, run/tokenizer.model, data/provenance.json), and retain a backup. Install PyTorch appropriate for the GPU, numpy, datasets==3.6.0, sentencepiece==0.2.1 and huggingface_hub==0.32.4.

```sh
cp research/arc_next/data/provenance.json /tmp/arc-next-original.json
python research/arc_next/resume_data.py /tmp/arc-next-original.json research/arc_next/data
python research/arc_next/billion_data.py --original-data research/arc_next/data --tokenizer research/arc_next/run/tokenizer.model --out /data/arc-next-billion-corpus
python research/arc_next/billion_train.py --checkpoint research/arc_next/run/checkpoint.pt --original-data research/arc_next/data --corpus /data/arc-next-billion-corpus --out /data/arc-next-billion-run --batch 64 --save-every 500 --max-steps 5000
```

Re-run the final command to resume from the latest atomic checkpoint. Keep the source checkpoint and source tokenizer available. Preserve the corpus manifest and file. Reduce the batch if necessary before the first run; batch is fixed across resumes. `--max-steps 0` runs to the target on dedicated compute. A billion packed uint16 tokens alone require about 2 GB on disk, excluding caches, checkpoints and dependencies. The new scripts have not yet been exercised on a GPU or the full corpus; perform a staged run and confirm actual measurements before budgeting a sustained campaign.

At intermediate milestones and after instruction tuning, evaluate with fresh unseen prompts:
```sh
python research/arc_next/evaluate_generalization.py /data/arc-next-billion-run/checkpoint.pt --n 20 --seed 2026112601 --out /data/arc-next-billion-run/evaluation.json
```
Do not reuse evaluation prompts for training. Require separate factual, qualitative, safety and privacy checks before release. A billion positions do not guarantee intelligence; the 4.24M parameter model is still very small. Do not publish an unverified checkpoint or claim the billion-token target is complete.
