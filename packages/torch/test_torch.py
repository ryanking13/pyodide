from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["torch"])
def test_import(selenium):
    import torch

    print(torch.__version__)


@run_in_pyodide(packages=["torch"])
def test_tensor_ops(selenium):
    import torch

    # Create tensor and do basic operations
    x = torch.tensor([1, 2, 3])
    y = torch.tensor([4, 5, 6])

    assert torch.equal(x + y, torch.tensor([5, 7, 9]))
    assert torch.equal(x - y, torch.tensor([-3, -3, -3]))
    assert torch.equal(x * y, torch.tensor([4, 10, 18]))
    assert torch.equal(x / y, torch.tensor([0.25, 0.4, 0.5]))


@run_in_pyodide(packages=["torch"])
def test_basic_train(selenium):
    import torch

    # Do basic classification training in torch
    class Net(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = torch.nn.Linear(2, 5)
            self.fc2 = torch.nn.Linear(5, 1)

        def forward(self, x):
            x = torch.relu(self.fc1(x))
            x = torch.sigmoid(self.fc2(x))
            return x

    net = Net()
    print(net)

    # Define the loss function and optimizer
    criterion = torch.nn.BCELoss()
    optimizer = torch.optim.SGD(net.parameters(), lr=0.01)

    # Train the network
    for _ in range(100):
        # Forward pass
        y_pred = net(torch.tensor([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=torch.float))
        y_true = torch.tensor([[0], [1], [1], [0]], dtype=torch.float)
        loss = criterion(y_pred, y_true)

        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    # Test the network
    y_pred = net(torch.tensor([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=torch.float))
    print(y_pred)

    assert torch.allclose(
        y_pred, torch.tensor([[0.0], [1.0], [1.0], [0.0]], dtype=torch.float), atol=0.1
    )
