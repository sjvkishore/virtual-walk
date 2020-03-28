import logging
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.decomposition import PCA
from tensorflow.keras import Model
from tensorflow.keras.layers import Dense, Input
from tensorflow.keras.optimizers import SGD

logger = logging.getLogger(__name__)


class FullModel:  # Not Model because it would shadow keras'
    def __init__(self, classes, load_path_PCA=None, load_path_NN=None, n_components=50, layers_NN=[50, 50], lr=0.01,
                 decay=1e-6, momentum=0.9, tensorboard_path=None):
        '''
        This model consists of a PCA and Neural Network. It has all the necessary methods to train and predict all the
        results.
        FLOW:
            1. Read data in the form
            [['stand', '1', '2', '3'],
             ['walk', '4', '5', '6']]

            2. Create model = FullModel()
            3. model.prepare_x_y(data)
            4. model.train_PCA(X)
            5. X_pca = model.predict_PCA(X)
            6. model.train_NN(X_pca, Y)
            7. model.predict(X_test)
        :param classes: list. Different classes the neural network has to be trained in. ['stand', 'walk']?
        :param load_path_PCA: str. If the PCA model has to be loaded from a location, the path to that location
        :param load_path_NN: str. If the Neural Network has to be loaded from a location, the path to that location
        :param n_components: int. The number of components the PCA has to consider. Also, the input dimension for the
        Neural Network
        :param layers_NN: list. This list specifies the architecture of the neural network. If [50, 50], two dense layers
        with 50 neurons each will be created. Only used if load_path_NN is None.
        :param lr, decay, momentum: float. Learning rate, decay and momentum for the SGD optimizer in the neural network
        :param tensorboard_path: str. The path to where the tensorboard logs will be saved. If set to none, no callbacks
        will be used.
        '''
        self.classes = classes
        self.n_classes = len(classes)
        if load_path_PCA is None:
            self.PCA = PCA(n_components)
        else:
            self.PCA = self.load_model(load_path_PCA)

        if load_path_NN is None:
            self.NN = self._get__NN(n_components, len(self.classes), layers_NN)
        else:
            self.NN = self.load_NN(load_path_NN)
        self._compile_NN(lr, decay, momentum)

        if tensorboard_path is not None:
            self.callbacks = self.create_callbacks(tensorboard_path)
        else:
            self.callbacks = None

    def predict(self, X):
        X_trans = self.predict_PCA(X)
        predicted_class = self.predict_NN(X_trans)
        return predicted_class

    def train_PCA(self, X, savepath=None):
        self.PCA.fit(X)
        if savepath is not None:
            self.save_PCA(savepath)

    def to_categorical(self, Y):
        if Y is not None:
            Y = np.array([self.classes.index(i) for i in Y])
            return tf.one_hot(Y, depth=self.n_classes)
        else:
            return None

    def _compile_NN(self, lr, decay, momentum):
        sgd = SGD(lr=lr, decay=decay, momentum=momentum, nesterov=True)
        self.NN.compile(loss='categorical_crossentropy', optimizer=sgd, metrics=['accuracy'])

    def train_NN(self, X_train, Y_train, batch_size, epochs, X_test=None, Y_test=None, is_one_hot=False, savepath=None,
                 verbose=0):
        '''
        Method to train the neural network.
        :param X_train, Y_train: ndarray. Training data. X contains the coordinates from PCA (shape (samples, n_components))
        and Y contains the labels (shape (samples,))
        :param batch_size: int.
        :param epochs: int.
        :param X_test, Y_test: ndarray.
        :param is_one_hot: bool. Format of the labels. These are converted to a one hot array in order to be fed to the NN.
        :param savepath: str.
        :param verbose: int.
        :return:
        '''
        if not is_one_hot:
            Y_train = self.to_categorical(Y_train)
            Y_test = self.to_categorical(Y_test)

        self.NN.fit(X_train, Y_train, validation_data=(X_test, Y_test), batch_size=batch_size, epochs=epochs,
                    callbacks=[self.callbacks], verbose=verbose)

        if X_test is not None:
            assert Y_test is not None, 'In order to evaluate the model Y_test must be passed to the training function'
            self.NN.evaluate(X_test, Y_test)

        if savepath is not None:
            self.save_NN(savepath)

    def predict_PCA(self, X):
        return self.PCA.transform(X)

    def predict_NN(self, X):
        Y = self.NN.predict(X)
        predicted_classes = np.argmax(Y, axis=1)
        return [self.classes[i] for i in predicted_classes]

    @staticmethod
    def _get__NN(input_dim, output_dim, layers):
        '''
        Creation of the neural network.
        :param input_dim: integer.
        :param output_dim: integer.
        :param layers: list. This list specifies the architecture of the neural network. If [50, 50], two dense layers
        with 50 neurons each will be created.
        :return: neural network model.
        '''
        inputs = Input(shape=(input_dim,))
        x = Dense(layers[0], activation='relu')(inputs)
        for layer in layers[1:]:
            x = Dense(layer, activation='relu')(x)
        outputs = Dense(output_dim, activation='sigmoid')(x)

        model = Model(inputs=inputs, outputs=outputs)
        return model

    def save_PCA(self, savepath):
        if savepath is None:
            current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
            savepath = Path(__file__).parents[1].joinpath('models/PCA_{}.pkl'.format(current_time))

        with open(savepath, 'wb') as file:
            pickle.dump(self.PCA, file)
        logging.debug('PCA model saved to ' + savepath)

    @staticmethod
    def load_model(path_model):
        with open(path_model, 'rb') as file:
            pickle_model = pickle.load(file)

        return pickle_model

    @staticmethod
    def load_NN(model_path):
        return tf.keras.models.load_model(model_path)

    def save_NN(self, savepath):
        self.NN.save(savepath)
        logging.debug('Neural network saved to ' + savepath)

    def prepare_x_y(self, data):
        Y = data[:, 0]
        X = data[:, 1:]
        return X, Y

    @staticmethod
    def create_callbacks(path):
        return tf.keras.callbacks.TensorBoard(log_dir=path, write_graph=True, histogram_freq=0, update_freq='epoch')

    def get_explained_variance_ratio(self):
        return sum(self.PCA.explained_variance_ratio_)


if __name__ == '__main__':
    from random import randint
    data = np.random.random((100, 50))
    classes = ['walk', 'stand']
    labels = [classes[randint(0, len(classes) - 1)] for _ in range(data.shape[0])]
    data_labels = np.empty((data.shape[0], data.shape[1] + 1), dtype=object)
    data_labels[:, 0] = labels
    data_labels[:, 1:] = data

    current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
    tb_path = Path(__file__).parents[1].joinpath('logs/{}/'.format(current_time))

    m = FullModel(classes, tensorboard_path=tb_path, n_components=10)

    X, Y = m.prepare_x_y(data_labels)
    m.train_PCA(X)
    X_pca = m.predict_PCA(X)
    m.train_NN(X_pca, Y, X_test=X_pca, Y_test=Y, batch_size=20, epochs=20, verbose=2)

    m.predict(X)