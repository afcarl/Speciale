#!bin/bash

if [ -z "$1" ]
   then
      echo "ERROR: Train file not specified."
      exit
fi

if [ -z "$2" ]
   then
      echo "ERROR: Dev file not specified."
      exit
fi


INPUT_FILE=$1
FEATURE_FILE=$INPUT_FILE'.feature'
GRAPH_FILE=$INPUT_FILE'.encoded'

DEV_INPUT_FILE=$2
DEV_FEATURE_FILE=$DEV_INPUT_FILE'.feature'
DEV_GRAPH_FILE=$DEV_INPUT_FILE'.encoded'

ALGORITHM=fourway_lstm_final
FEATURE_MODE=sentence

MODEL_PATH=models/$ALGORITHM'.model'

THEANO_FLAGS='floatX=float32,warn_float64=raise,optimizer_including=local_remove_all_assert' python code/parsing/train.py --features $FEATURE_FILE --sentences $GRAPH_FILE --dev_features $DEV_FEATURE_FILE --dev_sentences $DEV_GRAPH_FILE --model_path $MODEL_PATH --algorithm $ALGORITHM --feature_mode $FEATURE_MODE
