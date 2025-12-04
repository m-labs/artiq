"""Mediator for AWG device integration with ARTIQ experiments."""

from sipyco.pc_rpc import Client


class AWGMediator:
    """Mediator for AWG device RPC client."""

    def __init__(self, host, port=3274):
        """
        Initialize the AWG mediator.

        Args:
            host: Host address of the controller
            port: Port number of the controller (default: 3274)
        """
        self.host = host
        self.port = port
        self._client = None

    def _get_client(self):
        """Get or create RPC client."""
        if self._client is None:
            self._client = Client(self.host, self.port, "awg")
        return self._client

    def __getattr__(self, name):
        """Forward attribute access to the RPC client."""
        # Only forward non-private attributes
        if name.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        return getattr(self._get_client(), name)

    def close(self):
        """Close the RPC client connection."""
        if self._client is not None:
            self._client.close_rpc()
            self._client = None

