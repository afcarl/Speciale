import numpy as np
from theano import tensor as T
import theano
import pickle

class RNN():

    '''
    Fields:
    '''

    hidden_dimension = 5
    input_dimension = 50

    learning_rate = 0.01
    momentum = 0.1
    batch_size = 25

    error_margin = 0.0001
    
    '''
    Class methods:
    '''

    def __init__(self):
        self.W_final = np.random.rand(self.hidden_dimension*4+1)

        n_lstm_layers = 4
        
        self.W_forget = np.random.rand(n_lstm_layers, self.hidden_dimension, self.input_dimension*2 + self.hidden_dimension + 1)
        self.W_input = np.random.rand(n_lstm_layers, self.hidden_dimension, self.input_dimension*2 + self.hidden_dimension + 1)
        self.W_cell = np.random.rand(n_lstm_layers, self.hidden_dimension, self.input_dimension*2 + self.hidden_dimension + 1)
        self.W_output = np.random.rand(n_lstm_layers, self.hidden_dimension, self.input_dimension*2 + self.hidden_dimension + 1)


    def __chunk(self, l):
        return np.array(list(zip(*[iter(l)]*self.batch_size)))

        
    def __pad_sentences(self, sentence_list):
        longest_sentence = max([len(x) for x  in sentence_list])

        self.max_words = longest_sentence
        
        new_sentences = np.zeros((len(sentence_list), longest_sentence, len(sentence_list[0][0])))

        for i, sentence in enumerate(sentence_list):
            new_sentences[i, :len(sentence), :] = sentence

        return new_sentences

    def __pad_golds(self, sentence_labels):
        longest_sentence = max([len(x) for x  in sentence_labels])

        new_labels = np.zeros((len(sentence_labels), longest_sentence, longest_sentence+1))

        for i, sentence in enumerate(sentence_labels):
            for j,label in enumerate(sentence):
                new_labels[i,j,:label.shape[0]] = label

        return np.array(new_labels)

    
        
    '''
    Theano functions:
    '''

    # Prediction method for a single LSTM block:
    def __theano_lstm(self, x, h_prev, c_prev, W_forget, W_input, W_cell, W_output):

        input_vector = T.concatenate((x, h_prev))

        forget_gate = T.nnet.sigmoid(T.dot(W_forget, input_vector))
        input_gate = T.nnet.sigmoid(T.dot(W_input, input_vector))
        candidate_vector = T.tanh(T.dot(W_cell, input_vector))
        cell_state = forget_gate*c_prev + input_gate * candidate_vector

        output = T.nnet.sigmoid(T.dot(W_output, input_vector))
        h = output * T.tanh(cell_state)
        return h, cell_state


    # Prediction method for a layer of LSTM blocks:
    def __theano_lstm_layer(self, Vs, W_forget, W_input, W_cell, W_output, forwards=True):
        h0 = np.zeros(self.hidden_dimension)
        c0 = np.zeros(self.hidden_dimension)

        lstm_preds, _ = theano.scan(fn=self.__theano_lstm,
                            outputs_info=[h0,c0],
                            sequences=Vs,
                            non_sequences=[W_forget,
                                           W_input,
                                           W_cell,
                                           W_output],
                            go_backwards=not forwards)

        # Discard the cell values:
        return lstm_preds[0]

    def __pairwise_features(self, V, Vs, sentence_length):
        thingy, _ = theano.scan(fn=lambda x, y: T.concatenate([y,x,[1]]),
                                sequences=Vs,
                                non_sequences=V)
        
        #Make root feature and bias neuron:
        root_features = T.concatenate((V,T.ones(self.input_dimension + 1)))

        flat_version = thingy.flatten()
        with_root = T.concatenate((root_features, flat_version))
        in_shape = T.reshape(with_root, newshape=(sentence_length+1,self.input_dimension*2+1))
        return in_shape

    def __theano_out_node(self, H, W_o):
        output_with_bias = T.concatenate((H, [1]))
        return T.dot(W_o, output_with_bias)

    def __theano_predict_with_pad(self, Vs, sentence_length, W_final,
                                     W_forget, W_input, W_cell, W_output):
        preds = self.__theano_sentence_prediction(Vs, sentence_length, W_final, W_forget, W_input, W_cell, W_output)

        pad1 = T.zeros((sentence_length, self.max_words - sentence_length))
        pad2 = T.zeros((self.max_words - sentence_length, self.max_words + 1))

        padded_result = T.concatenate((preds, pad1), axis=1)
        padded_result = T.concatenate((padded_result, pad2), axis=0)        

        return padded_result

        
    def __theano_sentence_loss(self, Vs, sentence_length, gold, W_final,
                                     W_forget, W_input, W_cell, W_output):
        preds = self.__theano_sentence_prediction(Vs, sentence_length, W_final, W_forget, W_input, W_cell, W_output)

        gold = gold[:sentence_length, :sentence_length+1]
        losses = T.nnet.categorical_crossentropy(preds, gold)

        return T.sum(losses)


    def __theano_batch_loss(self, Vs, sentence_lengths,W_final, W_forget, W_input, W_cell, W_output, Gs):
        losses, __ = theano.scan(fn=self.__theano_sentence_loss,
                                outputs_info=None,
                                sequences=[Vs,sentence_lengths, Gs],
                                non_sequences=[W_final, W_forget, W_input, W_cell, W_output])

        return T.sum(losses)

    
    def __theano_batch_prediction(self, Vs, sentence_lengths, W_final, W_forget, W_input, W_cell, W_output):
        preds, __ = theano.scan(fn=self.__theano_predict_with_pad,
                                outputs_info=None,
                                sequences=[Vs,sentence_lengths],
                                non_sequences=[W_final, W_forget, W_input, W_cell, W_output])

        return preds
    
    def __theano_sentence_prediction(self, Vs, sentence_length, W_final,
                                     W_forget, W_input, W_cell, W_output):

        Vs = Vs[:sentence_length]

        #Make pairwise features:
        pairwise_vs, _ = theano.scan(fn=self.__pairwise_features,
                                  outputs_info=None,
                                  sequences=Vs,
                                  non_sequences=[Vs, sentence_length])

        
        lstm_sidewards_forwards, _ = theano.scan(fn=self.__theano_lstm_layer,
                                                 outputs_info=None,
                                                 sequences=pairwise_vs,
                                                 non_sequences=[W_forget[0], W_input[0], W_cell[0], W_output[0], 1])

        lstm_sidewards_backwards, _ = theano.scan(fn=self.__theano_lstm_layer,
                                                 outputs_info=None,
                                                 sequences=pairwise_vs,
                                                 non_sequences=[W_forget[1], W_input[1], W_cell[1], W_output[1], 0])

        transpose_vs = pairwise_vs.transpose(1,0,2)

        lstm_downwards_forwards, _ = theano.scan(fn=self.__theano_lstm_layer,
                                                 outputs_info=None,
                                                 sequences=transpose_vs,
                                                 non_sequences=[W_forget[2], W_input[2], W_cell[2], W_output[2], 1])

        lstm_downwards_backwards, _ = theano.scan(fn=self.__theano_lstm_layer,
                                                 outputs_info=None,
                                                 sequences=transpose_vs,
                                                 non_sequences=[W_forget[3], W_input[3], W_cell[3], W_output[3], 0])

        full_lstm = T.concatenate((lstm_sidewards_forwards, lstm_sidewards_forwards, lstm_downwards_forwards.transpose(1,0,2), lstm_downwards_backwards.transpose(1,0,2)), axis=2)

        flatter_lstm = T.reshape(full_lstm, newshape=(sentence_length*(sentence_length+1), self.hidden_dimension*4))

        outputs, _ = theano.scan(fn=self.__theano_out_node,
                                 sequences=flatter_lstm,
                                 non_sequences=W_final)
        
        matrix_outputs = T.reshape(outputs, newshape=(sentence_length,sentence_length+1))

        return T.nnet.softmax(matrix_outputs)


    def __theano_sgd(self, Vs, Ls, Gs,
                     W_final, W_forget,
                     W_input, W_cell, W_output,
                     W_final_prevupd, W_forget_prevupd,
                     W_input_prevupd, W_cell_prevupd,
                     W_output_prevupd):

        loss = self.__theano_batch_loss(Vs, Ls, W_final, W_forget, W_input, W_cell, W_output, Gs)

        grads = T.grad(loss, [W_final, W_forget, W_input, W_cell, W_output])


        newUpdFin = grads[0]*self.learning_rate + W_final_prevupd*self.momentum
        newUpdFor = grads[1]*self.learning_rate + W_forget_prevupd*self.momentum
        newUpdInp = grads[2]*self.learning_rate + W_input_prevupd*self.momentum
        newUpdCel = grads[3]*self.learning_rate + W_cell_prevupd*self.momentum
        newUpdOut = grads[4]*self.learning_rate + W_output_prevupd*self.momentum

        newFin = W_final - newUpdFin
        newFor = W_forget - newUpdFor
        newInp = W_input - newUpdInp
        newCel = W_cell - newUpdCel
        newOut = W_output - newUpdOut

        return newFin, newFor, newInp, newCel, newOut, newUpdFin, newUpdFor, newUpdInp, newUpdCel, newUpdOut
        
    def train(self, sentences, labels):
        lengths = np.array([len(s) for s in sentences])
        lengths = lengths.astype(np.int32)

        sentences = self.__pad_sentences(sentences)
        labels = self.__pad_golds(labels)

        length_chunks = self.__chunk(lengths)
        sentence_chunks = self.__chunk(sentences)
        label_chunks = self.__chunk(labels)

        Vs = T.dtensor4('Vs')
        Ls = T.imatrix('Ls')
        Gs = T.tensor4('Gs')
        W_forget = T.dtensor3('W_forget')
        W_input = T.dtensor3('W_input')
        W_cell = T.dtensor3('W_cell')
        W_output = T.dtensor3('W_output')
        W_final = T.dvector('W_final')

        w_forget_upd = np.zeros_like(self.W_forget)
        w_input_upd = np.zeros_like(self.W_input)
        w_cell_upd = np.zeros_like(self.W_cell)
        w_output_upd = np.zeros_like(self.W_output)
        w_final_upd = np.zeros_like(self.W_final)

        current_loss = self.__batch_loss(sentences, lengths, labels)
        prev_loss = current_loss +1

        iteration_counter = 1
 
        while(prev_loss - current_loss > self.error_margin and iteration_counter < 11):
            prev_loss = current_loss
            print("Running gradient descent at iteration "+str(iteration_counter)+". Current loss: "+str(prev_loss))
            iteration_counter += 1

            results, _ =  theano.scan(fn=self.__theano_sgd,
                                  outputs_info=[W_final, W_forget, W_input, W_cell, W_output,
                                                w_final_upd, w_forget_upd, w_input_upd, w_cell_upd, w_output_upd],
                                  sequences=[Vs, Ls, Gs],
                                  non_sequences=None)

            finalW_final = results[0][-1]
            finalW_forget = results[1][-1]
            finalW_input = results[2][-1]
            finalW_cell = results[3][-1]
            finalW_output = results[4][-1]

            cgraph = theano.function(inputs=[Vs, Ls, Gs, W_final, W_forget, W_input, W_cell, W_output],
                                     outputs=[finalW_final, finalW_forget, finalW_input, finalW_cell, finalW_output])

            newW_fin, newW_for, newW_inp, newW_cel, newW_out = cgraph(sentence_chunks, length_chunks, label_chunks, self.W_final,
                                                                    self.W_forget, self.W_input, self.W_cell, self.W_output)

            self.W_final = newW_fin
            self.W_forget = newW_for
            self.W_input = newW_inp
            self.W_cell = newW_cel
            self.W_output = newW_out

            current_loss = self.__batch_loss(sentences, lengths, labels)
            self.save(self.save_path)

    def __batch_loss(self, sentences, lengths, golds):
       
        Vs = T.dtensor3('Vs')
        Ls = T.ivector('Ls')
        W_forget = T.dtensor3('W_forget')
        W_input = T.dtensor3('W_input')
        W_cell = T.dtensor3('W_cell')
        W_output = T.dtensor3('W_output')
        W_final = T.dvector('W_final')
        Gs = T.tensor3('Gs')
        
        result = self.__theano_batch_loss(Vs, Ls, W_final, W_forget, W_input, W_cell, W_output, Gs)
        cgraph = theano.function(inputs=[Vs, Ls, Gs, W_final, W_forget, W_input, W_cell, W_output], on_unused_input='warn', outputs=result)

        print(np.array(sentences).shape)
        res = cgraph(sentences, lengths, golds, self.W_final, self.W_forget, self.W_input, self.W_cell, self.W_output)
        print(res.shape)

        return res

    def batch_predict(self, sentences):
        lengths = np.array([len(s) for s in sentences])
        lengths = lengths.astype(np.int32)

        sentences = self.__pad_sentences(sentences)

        Vs = T.dtensor3('Vs')
        Ls = T.ivector('Ls')
        W_forget = T.dtensor3('W_forget')
        W_input = T.dtensor3('W_input')
        W_cell = T.dtensor3('W_cell')
        W_output = T.dtensor3('W_output')
        W_final = T.dvector('W_final')
        
        result = self.__theano_batch_prediction(Vs, Ls, W_final, W_forget, W_input, W_cell, W_output)
        cgraph = theano.function(inputs=[Vs, Ls, W_final, W_forget, W_input, W_cell, W_output], on_unused_input='warn', outputs=result)

        res = cgraph(sentences, lengths, self.W_final, self.W_forget, self.W_input, self.W_cell, self.W_output)

        out_sentences = []
        for sentence, length in zip(res, lengths):
            out_sentences.append(sentence[:length, :length+1])

        return out_sentences

    
    #For testing:
    def single_predict(self, sentences, golds):

        #Pad the sentences to allow use of tensor rather than list in theano:
        lengths = [len(s) for s in sentences]
        sentences = self.__pad_sentences(sentences)
        golds = self.__pad_golds(golds)
        
        Vs = T.dtensor3('Vs')
        Ls = T.ivector('Ls')
        W_forget = T.dtensor3('W_forget')
        W_input = T.dtensor3('W_input')
        W_cell = T.dtensor3('W_cell')
        W_output = T.dtensor3('W_output')
        W_final = T.dvector('W_final')
        Gs = T.tensor3('Gs')
        
        result = self.__theano_sgd(Vs, Ls, Gs, W_final, W_forget, W_input, W_cell, W_output, W_final, W_forget, W_input, W_cell, W_output)
        cgraph = theano.function(inputs=[Vs, Ls, Gs, W_final, W_forget, W_input, W_cell, W_output], on_unused_input='warn', outputs=result)

        print(np.array(sentences).shape)
        res = cgraph(sentences, lengths, golds, self.W_final, self.W_forget, self.W_input, self.W_cell, self.W_output)
        print(res.shape)

        return res


    def save(self, filename):
        store_list = [self.W_final, self.W_forget, self.W_input, self.W_cell, self.W_output]
        
        outfile1 = open(filename, 'wb')
        pickle.dump(store_list, outfile1)
        outfile1.close()
        

        
    def load(self, filename):
        infile = open(filename, 'rb')
        store_list = pickle.load(infile)
        infile.close()

        self.W_final = store_list[0]
        self.W_forget = store_list[1]
        self.W_input = store_list[2]
        self.W_cell = store_list[3]
        self.W_output = store_list[4]

    
def fit(features, labels, model_path=None):

    model = RNN()
    model.save_path = model_path
    model.train(features, labels)
    
def predict(features, model_path=None):
    model = RNN()
    model.load(model_path)

    predictions = model.batch_predict(features)
    
    return predictions
