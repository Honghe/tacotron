from concurrent.futures import ProcessPoolExecutor
from functools import partial
import numpy as np
import os
import glob
from util import audio
from hparams import hparams as hp

def parse_trn(trn_file) -> list:
  """
  Example:
  000001	卡尔普#2陪外孙#1玩滑梯#4。
	ka2 er2 pu3 pei2 wai4 sun1 wan2 hua2 ti1
  :return:
  """
  trns = []
  with open(trn_file) as f:
    line = f.readline().strip()
    while line:
      idx = line.split('\t')[0]
      pinyin = f.readline().strip()
      line = f.readline().strip()
      trns.append([idx, pinyin])
  return trns

def build_from_path(in_dir, out_dir, num_workers=1, tqdm=lambda x: x):
  '''Preprocesses the biaobei48000 dataset from a given input path into a given output directory.

    Args:
      in_dir: The directory where you have downloaded the biaobei48000 dataset
      out_dir: The directory to write the output into
      num_workers: Optional number of worker processes to parallelize across
      tqdm: You can optionally pass tqdm to get a nice progress bar

    Returns:
      A list of tuples describing the training examples. This should be written to train.txt
  '''

  # We use ProcessPoolExecutor to parallize across processes. This is just an optimization and you
  # can omit it and just call _process_utterance on each input if you want.
  executor = ProcessPoolExecutor(max_workers=num_workers)
  futures = []
  index = 1

  trn_file = os.path.join(in_dir, 'ProsodyLabeling', '000001-010000.txt')
  trn_ids = parse_trn(trn_file)
  for idx, pinyin in trn_ids:
    wav_file = os.path.join(in_dir, 'Wave', idx + '.wav')
    task = partial(_process_utterance, out_dir, index, wav_file, pinyin)
    futures.append(executor.submit(task))
    index += 1
  return [future.result() for future in tqdm(futures) if future.result() is not None]


def _process_utterance(out_dir, index, wav_path, pinyin):
  '''Preprocesses a single utterance audio/text pair.

  This writes the mel and linear scale spectrograms to disk and returns a tuple to write
  to the train.txt file.

  Args:
    out_dir: The directory to write the spectrograms into
    index: The numeric index to use in the spectrogram filenames.
    wav_path: Path to the audio file containing the speech input
    pinyin: The pinyin of Chinese spoken in the input audio file

  Returns:
    A (spectrogram_filename, mel_filename, n_frames, text) tuple to write to train.txt
  '''

  # Load the audio to a numpy array:
  wav = audio.load_wav(wav_path)

  # rescale wav for unified measure for all clips
  wav = wav / np.abs(wav).max() * 0.999

  # trim silence
  wav = audio.trim_silence(wav)

  # Compute the linear-scale spectrogram from the wav:
  spectrogram = audio.spectrogram(wav).astype(np.float32)
  n_frames = spectrogram.shape[1]
  if n_frames > hp.max_frame_num:
    return None

  # Compute a mel-scale spectrogram from the wav:
  mel_spectrogram = audio.melspectrogram(wav).astype(np.float32)

  # Write the spectrograms to disk:
  spectrogram_filename = 'biaobei48000-spec-%05d.npy' % index
  mel_filename = 'biaobei48000-mel-%05d.npy' % index
  np.save(os.path.join(out_dir, spectrogram_filename), spectrogram.T, allow_pickle=False)
  np.save(os.path.join(out_dir, mel_filename), mel_spectrogram.T, allow_pickle=False)

  # Return a tuple describing this training example:
  return (spectrogram_filename, mel_filename, n_frames, pinyin)
