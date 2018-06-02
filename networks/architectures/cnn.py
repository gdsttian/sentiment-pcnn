import tensorflow as tf
from networks.architectures.base import NeuralNetwork


class VanillaCNN(NeuralNetwork):

    def __init__(
        self,
        vocabulary_words,
        embedding_size,
        words_per_news,
        bags_per_batch=1,
        bag_size=5,
        channels_count=200,
        window_size=7,
        dp=5,
        n_out=3,
        dropout=0.5):
        """
        vocabulary_words: int
            amount of words in vocabulary

        embedding_size: int
            word's vector dimention

        words_per_news: int
            max amount of words per news

        returns: tuple of tf.Tensor
            input_params, cost, labels

        channels_count: int
            amount of channels of conv kernels

        window_size: int
            conv kernel parameter

        dp: int
            dimension of the position description (relative to NER within context)

        Note: returned 'labels' has a CONVERTED LABELS, where values as follows:
            0 -- negative, 1 -- neutral, and 2 -- positive.
        """

        self.parameters = {
            "vocabulary_words": vocabulary_words,
            "embedding_size": embedding_size,
            "words_per_news": words_per_news,
            "bags_per_batch": bags_per_batch,
            "bag_size": bag_size,
            "channels_count": channels_count,
            "window_size": window_size,
            "dp": dp,
            "dropout": dropout
        }

        batch_size = bag_size * bags_per_batch
        dp = 1
        embedding_size_p = embedding_size + 2 * dp  # embedding + dp_1 + dp_2

        # Hidden state variables
        W = tf.Variable(tf.random_normal([channels_count, n_out]), dtype=tf.float32)
        bias = tf.Variable(tf.random_normal([n_out]), dtype=tf.float32)
        conv_filter = tf.Variable(tf.random_normal([window_size * embedding_size_p, 1, channels_count]), dtype=tf.float32)

        # Input placeholders
        x = tf.placeholder(dtype=tf.int32, shape=[batch_size, words_per_news])
        P1 = tf.placeholder(dtype=tf.float32, shape=[batch_size, words_per_news])
        P2 = tf.placeholder(dtype=tf.float32, shape=[batch_size, words_per_news])
        p1_ind = tf.placeholder(dtype=tf.int32, shape=[batch_size])  # left indices for each batch
        p2_ind = tf.placeholder(dtype=tf.int32, shape=[batch_size])  # right indices for each batch
        y = tf.placeholder(dtype=tf.int32, shape=[batch_size])
        E = tf.placeholder(dtype=tf.float32, shape=[vocabulary_words, embedding_size])
        # bernoulli = tf.distributions.Bernoulli(dropout, dtype=tf.float32)

        # Constants
        p_P1 = tf.reshape(P1, [batch_size, words_per_news, 1])
        p_P1 = tf.pad(p_P1, [[0, 0], [0, 0], [embedding_size, dp]])

        p_P2 = tf.reshape(P2, [batch_size, words_per_news, 1])
        p_P2 = tf.pad(p_P2, [[0, 0], [0, 0], [embedding_size+dp, 0]])

        # Apply embeding for input x indices
        e = tf.nn.embedding_lookup(E, x)

        e_p1p2 = tf.pad(e, [[0, 0], [0, 0], [0, 2*dp]])
        e_p1p2 = tf.add(e_p1p2, p_P1)
        e_p1p2 = tf.add(e_p1p2, p_P2)

        # Add padding embedding rows (reason -- have the same amount of rows after conv1d).
        left_padding = (window_size - 1) / 2
        right_padding = (window_size - 1) - left_padding
        e_p1p2 = tf.pad(e_p1p2, [[0, 0], [left_padding, right_padding], [0, 0]])

        # Concatenate rows of matrix
        bwc_line = tf.reshape(e_p1p2, [batch_size, (words_per_news + (window_size - 1)) * embedding_size_p, 1])
        bwc_conv = tf.nn.conv1d(bwc_line, conv_filter, embedding_size_p, "VALID", data_format="NHWC", name="conv")
        bwgc_conv = tf.reshape(bwc_conv, [batch_size, 1, words_per_news, channels_count])

        # Maxpool
        bwgc_mpool = tf.nn.max_pool(
                bwgc_conv,
                [1, 1, words_per_news, 1],
                [1, 1, words_per_news, 1],
                padding='VALID',
                data_format="NHWC")

        bc_mpool = tf.squeeze(bwgc_mpool, axis=[1, 2])
        bc_pmpool = tf.reshape(bc_mpool, [batch_size, channels_count])
        g = tf.tanh(bc_pmpool)

        # Apply Bernoulli mask for 'g'
        # r = bernoulli.sample(sample_shape=[1, 3*channels_count])
        # r_batch = tf.matmul(tf.constant(1, shape=[batch_size, 1], dtype=tf.float32), r)
        # masked_g = tf.multiply(g, r_batch)

        logits_unscaled = tf.matmul(g, W) + bias
        logits_unscaled_dropout = tf.nn.dropout(logits_unscaled, dropout)

        self.labels = tf.argmax(tf.nn.softmax(logits_unscaled), axis=1)

        cross_entropy = tf.nn.sparse_softmax_cross_entropy_with_logits(
                logits=logits_unscaled_dropout,
                labels=y)
        cross_entropy_per_bag = tf.reshape(cross_entropy, [bags_per_batch, bag_size])

        self.cost = tf.reduce_max(cross_entropy_per_bag, axis=1)

        self.x = x
        self.P1 = P1
        self.P2 = P2
        self.p1_ind = p1_ind
        self.p2_ind = p2_ind
        self.y = y
        self.E = E

    @property
    def Cost(self):
        return self.cost

    @property
    def Labels(self):
        return self.labels

    @property
    def ParametersDictionary(self):
        return self.parameters