import tensorflow as tf
import tensorflow.contrib.layers as layers
import os
from pathlib import Path

from tensorflow.examples.tutorials.mnist import input_data
from infogan.misc_utils import parse_math

def variables_in_current_scope():
    return tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=tf.get_variable_scope().name)


def scope_variables(name):
    with tf.variable_scope(name):
        return variables_in_current_scope()


def leaky_rectify(x, leakiness=0.01):
    assert leakiness <= 1
    ret = tf.maximum(x, leakiness * x)
    return ret


def identity(x):
    return x


def conv_batch_norm(inputs,
                    name="batch_norm",
                    is_training=True,
                    trainable=True,
                    epsilon=1e-5):

    return tf.contrib.layers.batch_norm(inputs,
                                            decay=0.9,
                                            updates_collections=None,
                                            epsilon=epsilon,
                                            scale=True,
                                            is_training=is_training,
                                            scope=name)

NONLINEARITY_NAME_TO_F = {
    'lrelu': leaky_rectify,
    'relu': tf.nn.relu,
    'sigmoid': tf.nn.sigmoid,
    'tanh': tf.nn.tanh,
    'identity': tf.identity,
}


def parse_conv_params(params):
    nonlinearity = 'relu'
    if len(params) == 4:
        params, nonlinearity = params[:-1], params[-1]
    nkernels, stride, num_outputs = [parse_math(p) for p in params]

    return nkernels, stride, num_outputs, nonlinearity

def run_network(inpt, string, is_training, debug=False, strip_batchnorm_from_last_layer=False):
    maybe_fc_batch_norm   = layers.batch_norm
    maybe_conv_batch_norm = conv_batch_norm

    if debug:
        print ("%s architecture" % (tf.get_variable_scope().name,))

    layer_idx = 0

    out = inpt
    layer_strs = string.split(",")
    for i, layer in enumerate(layer_strs):
        if i + 1 == len(layer_strs) and strip_batchnorm_from_last_layer:
            maybe_fc_batch_norm   = None
            maybe_conv_batch_norm = None

        if layer.startswith("conv:"):
            nkernels, stride, num_outputs, nonlinearity_str = parse_conv_params(layer[len("conv:"):].split(":"))
            nonlinearity = NONLINEARITY_NAME_TO_F[nonlinearity_str]

            out = layers.convolution2d(
                out,
                num_outputs=num_outputs,
                kernel_size=nkernels,
                stride=stride,
                normalizer_params={"is_training": is_training},
                normalizer_fn=maybe_conv_batch_norm,
                activation_fn=nonlinearity,
                scope='layer_%d' % (layer_idx,)
            )
            layer_idx += 1

            if debug:
                print ("Convolution with nkernels=%d, stride=%d, num_outputs=%d followed by %s" %
                        (nkernels, stride, num_outputs, nonlinearity_str))

        elif layer.startswith("deconv:"):
            nkernels, stride, num_outputs, nonlinearity_str = parse_conv_params(layer[len("deconv:"):].split(":"))
            nonlinearity = NONLINEARITY_NAME_TO_F[nonlinearity_str]

            out = layers.convolution2d_transpose(
                out,
                num_outputs=num_outputs,
                kernel_size=nkernels,
                stride=stride,
                activation_fn=nonlinearity,
                normalizer_fn=maybe_conv_batch_norm,
                normalizer_params={"is_training": is_training},
                scope='layer_%d' % (layer_idx,)
            )
            layer_idx += 1
            if debug:
                print ("Deconvolution with nkernels=%d, stride=%d, num_outputs=%d followed by %s" %
                        (nkernels, stride, num_outputs, nonlinearity_str))
        elif layer.startswith("fc:"):
            params = layer[len("fc:"):].split(":")
            nonlinearity_str = 'relu'
            if len(params) == 2:
                params, nonlinearity_str = params[:-1], params[-1]
            num_outputs = parse_math(params[0])
            nonlinearity = NONLINEARITY_NAME_TO_F[nonlinearity_str]

            out = layers.fully_connected(
                out,
                num_outputs=num_outputs,
                activation_fn=nonlinearity,
                normalizer_fn=maybe_fc_batch_norm,
                normalizer_params={"is_training": is_training, "updates_collections": None},
                scope='layer_%d' % (layer_idx,)
            )
            layer_idx += 1
            if debug:
                print ("Fully connected with num_outputs=%d followed by %s" %
                        (num_outputs, nonlinearity_str))
        elif layer.startswith("reshape:"):
            params = layer[len("reshape:"):].split(":")
            dims = [parse_math(dim) for dim in params]
            out = tf.reshape(out, [-1] + dims)
            if debug:
                print("Reshape to %r" % (dims,))
        else:
            raise ValueError("Could not parse layer description: %r" % (layer,))
    if debug:
        print("")
    return out



def load_mnist_dataset():
    # User home directory
    home = str(Path.home())
    DATA_ROOT_DIR = os.path.join(home, "dataset", "MNIST_data")

    mnist = input_data.read_data_sets(DATA_ROOT_DIR, one_hot=False) # Loading the training, validation & testing dataset
    pixel_height = 28
    pixel_width = 28
    n_channels = 1
    for dset in [mnist.train, mnist.validation, mnist.test]:
        num_images = len(dset.images)
        dset.images.shape = (num_images, pixel_height, pixel_width, n_channels)
    return mnist.train.images


NOOP = tf.no_op()
