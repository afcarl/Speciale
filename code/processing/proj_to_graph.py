import imp
import argparse
import numpy as np

io = imp.load_source('io', 'code/common/io.py')
definitions = imp.load_source('definitions', 'code/common/definitions.py')
conll_column_headers = definitions.conll_column_headers

parser = argparse.ArgumentParser(description="Convert a reference-to-head form to a graph-format.")
parser.add_argument("--infile", help="Input filepath (CoNLL format).", required=True)
parser.add_argument("--outfile", help="Output filepath (CoNLL format).", required=True)
args = parser.parse_args()

def softmax(x):
    return np.exp(x) / np.sum(np.exp(x), axis=0)

def process_graph(text_graph, current_sentence_length):
    elements = [float(e.split(':')[1]) for e in text_graph.split(' ')]
    elements = softmax(elements)
    indices = [int(e.split(':')[0]) for e in text_graph.split(' ')]
    
    output_list = ['0.0']*(current_sentence_length+1)

    for n,e in zip(indices, elements):
        output_list[n] = str(e)
    
    return output_list
        

def short_conll_list_to_dict(token_list, current_sentence_length):
    global conll_column_headers

    token_dict = {}
    for i in range(8):
        header_name = conll_column_headers[i][0]
        header_type = conll_column_headers[i][1]
        token_dict[header_name] =  header_type(token_list[i])

    for i in range(8,10):
        header_name = conll_column_headers[i][0]
        header_type = conll_column_headers[i][1]
        token_dict[header_name] =  '_'

    graph_name = conll_column_headers[10][0]
    graph_type = conll_column_headers[10][0]
    token_dict[graph_name] = process_graph(token_list[8], current_sentence_length)

    return token_dict

def read_short_conll_sentences(filename):    
    sentences = [[]]
    lines_to_process = []

    for line in open(filename, 'r+'):
        stripped = line.strip()

        if stripped:
            lines_to_process.append(stripped)
            
        else:
            for l in lines_to_process:
                token_list = l.split('\t')
                token_dict = short_conll_list_to_dict(token_list, len(lines_to_process))
                sentences[-1].append(token_dict)

            lines_to_process = []
            sentences.append([])

    while sentences[-1] == []:
        sentences = sentences[:-1]

    return sentences

sentences = read_short_conll_sentences(args.infile)

io.write_conll_sentences(sentences, args.outfile)
