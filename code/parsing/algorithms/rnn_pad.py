import theano
from theano import tensor as T
import numpy as np
import pickle

class RNN():

    '''
    Fields:
    '''

    W_output = None
    
    max_words = None
    input_dimension = 5
    hidden_dimension = 5
    
    '''
    Class methods:
    '''

    def __init__(self, max_words):
        self.max_words = max_words

        self.W_forward_forget = theano.shared(np.array(np.random.rand(self.hidden_dimension, self.input_dimension + self.hidden_dimension + 1), dtype=theano.config.floatX))
        self.W_backward_forget = theano.shared(np.array(np.random.rand(self.hidden_dimension, self.input_dimension + self.hidden_dimension + 1), dtype=theano.config.floatX))

        self.W_forward_input = theano.shared(np.array(np.random.rand(self.hidden_dimension, self.input_dimension + self.hidden_dimension + 1), dtype=theano.config.floatX))
        self.W_backward_input = theano.shared(np.array(np.random.rand(self.hidden_dimension, self.input_dimension + self.hidden_dimension + 1), dtype=theano.config.floatX))

        self.W_forward_cell = theano.shared(np.array(np.random.rand(self.hidden_dimension, self.input_dimension + self.hidden_dimension + 1), dtype=theano.config.floatX))
        self.W_backward_cell = theano.shared(np.array(np.random.rand(self.hidden_dimension, self.input_dimension + self.hidden_dimension + 1), dtype=theano.config.floatX))

        self.W_forward_output = theano.shared(np.array(np.random.rand(self.hidden_dimension, self.input_dimension + self.hidden_dimension + 1), dtype=theano.config.floatX))
        self.W_backward_output = theano.shared(np.array(np.random.rand(self.hidden_dimension, self.input_dimension + self.hidden_dimension + 1), dtype=theano.config.floatX))

        self.W_final = theano.shared(np.array(np.random.rand(self.max_words* (self.max_words +1), (self.max_words * self.hidden_dimension*2) +1), dtype=theano.config.floatX))

    '''
    Outward functions:
    '''

    def predict(self, sentence_list):
        results = self.__theano_batch_predict(sentence_list)

        return results
        
    '''
    Theano functions:
    '''

    def __theano_lstm(self, x, h_prev, c_prev, W_forget, W_input, W_cell, W_output):

        input_vector = T.concatenate((x, h_prev, [1]))

        forget_gate = T.nnet.sigmoid(T.dot(W_forget, input_vector))
        input_gate = T.nnet.sigmoid(T.dot(W_input, input_vector))
        candidate_vector = T.tanh(T.dot(W_cell, input_vector))
        cell_state = forget_gate*c_prev + input_gate * candidate_vector

        output = T.nnet.sigmoid(T.dot(W_output, input_vector))
        h = output * T.tanh(cell_state)
        return h, cell_state


    def __theano_forward_lstm_layer(self, Vs):
        h0 = np.zeros(self.hidden_dimension)
        c0 = np.zeros(self.hidden_dimension)

        forward_lstm, _ = theano.scan(fn=self.__theano_lstm,
                            outputs_info=[h0,c0],
                            sequences=Vs,
                            non_sequences=[self.W_forward_forget,
                                           self.W_forward_input,
                                           self.W_forward_cell,
                                           self.W_forward_output])

        forward_hs = forward_lstm[0]
        return forward_hs

    def __theano_backward_lstm_layer(self, Vs):
        h0 = np.zeros(self.hidden_dimension)
        c0 = np.zeros(self.hidden_dimension)

        backward_lstm, _ = theano.scan(fn=self.__theano_lstm,
                            outputs_info=[h0,c0],
                            sequences=Vs,
                            non_sequences=[self.W_backward_forget,
                                           self.W_backward_input,
                                           self.W_backward_cell,
                                           self.W_backward_output],
                            go_backwards=True)

        backward_hs = backward_lstm[0]
        return backward_hs


    def __theano_predict_inner(self, padded_sentence_vector, sentence_length):
        sentence_vector = padded_sentence_vector[:sentence_length]
        forward_hs = self.__theano_forward_lstm_layer(sentence_vector)
        backward_hs = self.__theano_backward_lstm_layer(sentence_vector)

        padding = T.zeros((self.max_words - sentence_length, 2*self.hidden_dimension))

        hidden_with_bias = T.concatenate((forward_hs, backward_hs), axis=1)
        hidden_with_bias_and_padding = T.concatenate((hidden_with_bias, padding), axis=0)
        
        flat = T.concatenate((T.flatten(hidden_with_bias_and_padding), [1]))
        flat_result = T.dot(self.W_final, flat)
        shaped_result = flat_result.reshape((self.max_words, self.max_words +1))

        result = shaped_result[:sentence_length, :sentence_length+1]

        return T.nnet.softmax(result)
        
    def __theano_predict(self, sentence):
        V = T.dmatrix('V')

        result = self.__theano_predict_inner(V, len(sentence))
        c_graph = theano.function(inputs=[V], outputs=result, on_unused_input='warn')

        return c_graph(sentence)

    def __shitty_theano_predict_inner(self, padded_sentence_vector, sentence_length):
        actual_result = self.__theano_predict_inner(padded_sentence_vector, sentence_length)

        pad1 = T.zeros((sentence_length, self.max_words - sentence_length))
        pad2 = T.zeros((self.max_words - sentence_length, self.max_words + 1))

        padded_result = T.concatenate((actual_result, pad1), axis=1)
        padded_result = T.concatenate((padded_result, pad2), axis=0)        

        return padded_result
    
    def __theano_batch_predict_inner(self, sentence_vectors, sentence_lengths):
        results, _ = theano.scan(fn=self.__shitty_theano_predict_inner,
                            outputs_info=None,
                            sequences=[sentence_vectors, sentence_lengths],
                            non_sequences=None)
        return results
        
    
    def __theano_batch_predict(self, sentence_list):
        padded_sentences = self.__pad_sentences(sentence_list)

        Vs = T.dtensor3('Vs')
        ls = theano.shared(np.array([len(sentence) for sentence in sentence_list]))

        results = self.__theano_batch_predict_inner(Vs, ls)
        c_graph = theano.function(inputs=[Vs], outputs = results)
        
        theano_result = c_graph(padded_sentences)
    
        actual_result = []
        for m,l in zip(theano_result, ls.get_value()):
            actual_result.append(m[:l, :l+1])

        return actual_result
    

    def __pad_sentences(self, sentence_list):
        longest_sentence = max([len(x) for x  in sentence_list])

        new_sentences = np.zeros((len(sentence_list), longest_sentence, len(sentence_list[0][0])))

        for i, sentence in enumerate(sentence_list):
            new_sentences[i, :len(sentence), :] = sentence

        return new_sentences


def __pad_labels(sentence_labels):
    longest_sentence = max([len(x) for x  in sentence_labels])

    new_labels = np.zeros((len(sentence_labels), longest_sentence, longest_sentence+1))

    for i, sentence in enumerate(sentence_labels):
        for j,label in enumerate(sentence):
            new_labels[i,j,:label.shape[0]] = label

    return np.array(new_labels)
        
    
    
def fit(sentence_instances, sentence_labels, model_path=None, save_every_iteration=False):

    padded_labels = __pad_labels(sentence_labels)
    model = RNN(padded_labels.shape[1])

    for q in model.predict(sentence_instances[:20]):
        print(q.shape)
