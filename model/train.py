from pathlib import Path
import pickle

from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression


def main():
    X, y = load_iris(return_X_y=True)

    model = LogisticRegression(max_iter=300)
    model.fit(X, y)

    output_path = Path(__file__).resolve().parent / "model.pkl"
    with open(output_path, "wb") as f:
        pickle.dump(model, f)

    print(f"Model saved to {output_path}")


if __name__ == "__main__":
    main()