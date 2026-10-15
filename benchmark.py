"""Run with .venv/Scripts/python.exe benchmark.py [--model] [--compile]."""
import argparse
import time
import torch
from core import model_snapshot


def main():
    parser = argparse.ArgumentParser(description='Verify GPU compilation or benchmark cached VoxCPM weights.')
    parser.add_argument('--model', action='store_true')
    parser.add_argument('--compile', action='store_true')
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable.')
    print(f'PyTorch {torch.__version__}; GPU: {torch.cuda.get_device_name(0)}', flush=True)
    if not args.model:
        import triton
        print(f'Triton {triton.__version__}', flush=True)
        def calculation(x):
            return x.sin() + x.cos()
        x = torch.randn(4096, device='cuda')
        compiled = torch.compile(calculation, fullgraph=True)
        torch.testing.assert_close(compiled(x), calculation(x))
        torch.cuda.synchronize()
        print('CUDA torch.compile check passed.', flush=True)
        return
    from voxcpm import VoxCPM
    started = time.perf_counter()
    model = VoxCPM.from_pretrained(model_snapshot(local_files_only=True), load_denoiser=False,
                                   local_files_only=True, optimize=args.compile)
    torch.cuda.synchronize()
    print(f'Model preparation: {time.perf_counter() - started:.2f}s', flush=True)
    for i in range(3):
        torch.manual_seed(42)
        torch.cuda.synchronize()
        started = time.perf_counter()
        wav = model.generate(text='The morning light fell across the open book. A new story was about to begin.',
                             inference_timesteps=20, cfg_value=2.0)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        duration = len(wav) / model.tts_model.sample_rate
        print(f'Run {i+1}: {elapsed:.2f}s for {duration:.2f}s audio; RTF {elapsed/duration:.3f}', flush=True)


if __name__ == '__main__':
    main()
