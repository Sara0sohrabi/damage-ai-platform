"""Load the existing trusted artifact, including its historical Cython module alias."""
import sys
import joblib


def load_model(path):
    try:
        return joblib.load(path)
    except ModuleNotFoundError as exc:
        if exc.name != '_loss':
            raise
        # The supplied artifact references Cython's short module name. Map it to
        # the same scikit-learn implementation; no model weights are changed.
        import sklearn._loss._loss as sklearn_loss
        previous = sys.modules.get('_loss')
        sys.modules['_loss'] = sklearn_loss
        try:
            return joblib.load(path)
        finally:
            if previous is None:
                sys.modules.pop('_loss', None)
            else:
                sys.modules['_loss'] = previous
