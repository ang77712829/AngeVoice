import warnings

import torch

from kokoro_tts.engine import _single_layer_rnn_dropout_compat


def test_single_layer_rnn_dropout_compat_sets_noop_dropout_to_zero():
    with _single_layer_rnn_dropout_compat():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            layer = torch.nn.LSTM(4, 4, num_layers=1, dropout=0.2)

    assert layer.dropout == 0.0
    assert not any("dropout option adds dropout" in str(item.message) for item in caught)
