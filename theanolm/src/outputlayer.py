#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy
from collections import OrderedDict
import theano.tensor as tensor

from matrixfunctions import normalized_weight

class OutputLayer(object):
	""" Output Layer
	
	The output layer is a simple softmax layer that outputs the word
	probabilities.
	"""

	def __init__(self, in_size, out_size):
		"""Initializes the parameters for a feed-forward layer of a neural
		network.

		:type options: dict
		:param options: a dictionary of training options

		:type in_size: int
		:param options: number of input connections
		
		:type out_size: int
		:param options: size of the output
		"""

		# Create the parameters.
		self.init_params = OrderedDict()

		self.init_params['output_W'] = \
				normalized_weight(in_size, out_size, scale=0.01, ortho=True)

		self.init_params['output_b'] = \
				numpy.zeros((out_size,)).astype('float32')

	def create_minibatch_structure(self, theano_params, layer_input):
		""" Creates output layer structure.

		In mini-batch training the input is 3-dimensional: the first dimension
		is the time step, the second dimension are the sequences, and the third
		dimension is the word projection. Before taking the softmax and
		returning the probabilities, the first two dimensions are combined.

		:type theano_params: dict
		:param theano_params: shared Theano variables

		:type layer_input: theano.tensor.var.TensorVariable
		:param layer_input: symbolic matrix that describes the output of the
		previous layer

		:rtype: theano.tensor.var.TensorVariable
		:returns: symbolic matrix that describes the output of this layer
		"""

		preact = tensor.dot(layer_input, theano_params['output_W']) \
				+ theano_params['output_b']
		
		num_time_steps = preact.shape[0]
		num_sequences = preact.shape[1]
		word_projection_dim = preact.shape[2]
		preact = preact.reshape([num_time_steps * num_sequences,
		                         word_projection_dim])
		
		return tensor.nnet.softmax(preact)

	def create_onestep_structure(self, theano_params, layer_input):
		""" Creates output layer structure.
		
		This function is used for creating a text generator. The input is
		2-dimensional: the first dimension is the sequence and the second is
		the word projection.

		:type theano_params: dict
		:param theano_params: shared Theano variables

		:type layer_input: theano.tensor.var.TensorVariable
		:param layer_input: symbolic matrix that describes the output of the
		previous layer

		:rtype: theano.tensor.var.TensorVariable
		:returns: symbolic matrix that describes the output of this layer
		"""

		preact = tensor.dot(layer_input, theano_params['output_W']) \
				+ theano_params['output_b']
		
		return tensor.nnet.softmax(preact)
