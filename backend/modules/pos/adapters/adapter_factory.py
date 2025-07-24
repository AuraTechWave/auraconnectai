from typing import Dict, Any
from .base_adapter import BasePOSAdapter
from .square_adapter import SquareAdapter
from .toast_adapter import ToastAdapter
from .clover_adapter import CloverAdapter
from ..enums.pos_enums import POSVendor


class AdapterFactory:
    @staticmethod
    def create_adapter(
        vendor: POSVendor, credentials: Dict[str, Any]
    ) -> BasePOSAdapter:
        adapters = {
            POSVendor.SQUARE: SquareAdapter,
            POSVendor.TOAST: ToastAdapter,
            POSVendor.CLOVER: CloverAdapter,
        }

        adapter_class = adapters.get(vendor)
        if not adapter_class:
            raise ValueError(f"Unsupported POS vendor: {vendor}")

        return adapter_class(credentials)
