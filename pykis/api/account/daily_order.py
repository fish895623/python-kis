from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pykis.__env__ import TIMEZONE
from pykis.api.account.order import (
    ORDER_CONDITION,
    ORDER_EXECUTION,
    ORDER_TYPE,
    KisOrder,
    resolve_domestic_order_condition,
)
from pykis.api.base.account import KisAccountBase
from pykis.api.base.account_product import KisAccountProductBase
from pykis.api.stock.info import COUNTRY_TYPE, resolve_market
from pykis.api.stock.market import (
    CURRENCY_TYPE,
    MARKET_TYPE,
    get_market_currency,
    get_market_timezone,
)
from pykis.client.account import KisAccountNumber
from pykis.client.page import KisPage
from pykis.responses.dynamic import KisDynamic, KisList, KisTransform
from pykis.responses.response import KisPaginationAPIResponse
from pykis.responses.types import KisAny, KisBool, KisDecimal, KisString
from pykis.utils.cache import cached, set_cache

if TYPE_CHECKING:
    from pykis.kis import PyKis


class KisDailyOrder(KisDynamic, KisAccountProductBase):
    """한국투자증권 일별 체결내역"""

    time: datetime
    """시간 (현지시간)"""
    time_kst: datetime
    """시간 (한국시간)"""

    symbol: str
    """종목코드"""
    market: MARKET_TYPE
    """상품유형타입"""
    account_number: KisAccountNumber
    """계좌번호"""

    order_number: KisOrder
    """주문번호"""

    name: str
    """종목명"""

    type: ORDER_TYPE
    """주문유형"""

    price: Decimal | None
    """체결단가"""
    unit_price: Decimal | None
    """주문단가"""

    @property
    def order_price(self) -> Decimal | None:
        """주문단가"""
        return self.unit_price

    quantity: Decimal
    """주문수량"""

    @property
    def qty(self) -> Decimal:
        """주문수량"""
        return self.quantity

    executed_quantity: Decimal
    """체결수량"""

    pending_quantity: Decimal
    """미체결수량"""

    rejected_quantity: Decimal
    """거부수량"""

    @property
    def executed_qty(self) -> Decimal:
        """체결수량"""
        return self.executed_quantity

    @property
    def executed_amount(self) -> Decimal:
        """체결금액"""
        return (self.executed_quantity * self.price) if self.price else Decimal(0)

    @property
    def pending_qty(self) -> Decimal:
        """미체결수량"""
        return self.pending_quantity

    @property
    def rejected_qty(self) -> Decimal:
        """거부수량"""
        return self.rejected_quantity

    condition: ORDER_CONDITION | None
    """주문조건"""
    execution: ORDER_EXECUTION | None
    """체결조건"""

    cancelled: bool
    """취소여부"""

    currency: CURRENCY_TYPE
    """통화"""


class KisDailyOrders(KisDynamic, KisAccountBase):
    """한국투자증권 일별 체결내역"""

    account_number: KisAccountNumber
    """계좌번호"""

    orders: list[KisDailyOrder]
    """일별 체결내역"""

    def __getitem__(self, key: int | KisOrder | str) -> KisDailyOrder:
        """인덱스 또는 주문번호로 주문을 조회합니다."""
        if isinstance(key, int):
            return self.orders[key]
        elif isinstance(key, str):
            for order in self.orders:
                if order.symbol == key:
                    return order
        elif isinstance(key, KisOrder):
            for order in self.orders:
                if order.order_number == key:
                    return order

        raise KeyError(key)

    def order(self, key: KisOrder | str) -> KisDailyOrder | None:
        """주문번호 또는 종목코드로 주문을 조회합니다."""
        if isinstance(key, str):
            for order in self.orders:
                if order.symbol == key:
                    return order
        elif isinstance(key, KisOrder):
            for order in self.orders:
                if order.order_number == key:
                    return order

        return None

    def __len__(self) -> int:
        return len(self.orders)

    def __iter__(self):
        return iter(self.orders)

    def __repr__(self) -> str:
        nl = "\n    "
        nll = "\n        "
        return f"{self.__class__.__name__}({nl}account_number={self.account_number!r},{nl}orders=[{nll}{f',{nll}'.join(map(repr, self.orders))}{nl}]\n)"


DOMESTIC_EXCHANGE_CODE_MAP: dict[str, tuple[COUNTRY_TYPE, MARKET_TYPE | None, ORDER_CONDITION | None]] = {
    "01": ("KR", "KRX", None),
    "02": ("KR", "KRX", None),
    "03": ("KR", "KRX", None),
    "04": ("KR", "KRX", None),
    "05": ("KR", "KRX", None),
    "06": ("KR", "KRX", None),
    "07": ("KR", "KRX", None),
    "21": ("KR", "KRX", None),
    "51": ("HK", None, None),
    "52": ("CN", "SHAA", None),
    "53": ("CN", "SZAA", None),
    "54": ("HK", None, None),
    "55": ("US", None, None),
    "56": ("JP", "TKSE", None),
    "57": ("CN", "SHAA", None),
    "58": ("CN", "SZAA", None),
    "59": ("VN", None, None),
    "61": ("KR", "KRX", "before"),
    "64": ("KR", "KRX", None),
    "65": ("KR", "KRX", None),
    "81": ("KR", "KRX", "extended"),
}


class KisDomesticDailyOrder(KisDynamic, KisAccountProductBase):
    """한국투자증권 국내 일별 체결내역"""

    time: datetime
    """시간 (현지시간)"""
    time_kst: datetime = KisTransform(
        lambda x: datetime.strptime(x["ord_dt"] + x["ord_tmd"], "%Y%m%d%H%M%S").replace(tzinfo=TIMEZONE)
    )()
    """시간 (한국시간)"""

    symbol: str = KisString["pdno"]
    """종목코드"""

    country: COUNTRY_TYPE
    """국가"""

    @property
    @cached
    def market(self) -> MARKET_TYPE:
        """상품유형타입"""
        return resolve_market(
            self.kis,
            symbol=self.symbol,
            market=self.country,
        )

    account_number: KisAccountNumber
    """계좌번호"""

    branch: str = KisString["ord_gno_brno"]
    """지점코드"""
    number: str = KisString["odno"]
    """주문번호"""

    @property
    @cached
    def order_number(self) -> KisOrder:
        """주문번호"""
        return KisOrder(
            account_number=self.account_number,
            symbol=self.symbol,
            market=self.market,
            branch=self.branch,
            number=self.number,
            time_kst=self.time_kst,
            kis=self.kis,
        )

    name: str = KisString["prdt_name"]
    """종목명"""

    type: ORDER_TYPE = KisAny(lambda x: "buy" if x == "02" else "sell")["sll_buy_dvsn_cd"]
    """주문유형"""

    price: Decimal | None = KisDecimal["avg_prvs"]
    """체결단가"""
    unit_price: Decimal | None = KisDecimal["ord_unpr"]
    """주문단가"""

    @property
    def order_price(self) -> Decimal | None:
        """주문단가"""
        return self.unit_price

    quantity: Decimal = KisDecimal["ord_qty"]
    """주문수량"""

    @property
    def qty(self) -> Decimal:
        """주문수량"""
        return self.quantity

    executed_quantity: Decimal = KisDecimal["tot_ccld_qty"]
    """체결수량"""

    pending_quantity: Decimal = KisDecimal["rmn_qty"]
    """미체결수량"""

    rejected_quantity: Decimal = KisDecimal["rjct_qty"]
    """거부수량"""

    @property
    def executed_qty(self) -> Decimal:
        """체결수량"""
        return self.executed_quantity

    @property
    def executed_amount(self) -> Decimal:
        """체결금액"""
        return (self.executed_quantity * self.price) if self.price else Decimal(0)

    @property
    def pending_qty(self) -> Decimal:
        """미체결수량"""
        return self.pending_quantity

    @property
    def rejected_qty(self) -> Decimal:
        """거부수량"""
        return self.rejected_quantity

    condition: ORDER_CONDITION | None = None
    """주문조건"""
    execution: ORDER_EXECUTION | None = None
    """체결조건"""

    cancelled: bool = KisTransform(lambda x: x == "Y")["ccld_yn"]
    """취소여부"""

    @property
    @cached
    def currency(self) -> CURRENCY_TYPE:
        """통화"""
        return get_market_currency(self.market)

    def __pre_init__(self, data: dict[str, Any]):
        super().__pre_init__(data)

        country, market, condition = DOMESTIC_EXCHANGE_CODE_MAP[data["excg_dvsn_cd"]]

        self.country = country

        if market:
            set_cache(self, "market", market)
            set_cache(self, "currency", get_market_currency(market))

        self.condition = condition

    def __post_init__(self):
        super().__post_init__()

        self.time = self.time_kst.astimezone(get_market_timezone(self.market))


class KisDomesticDailyOrders(KisPaginationAPIResponse, KisDailyOrders):
    """한국투자증권 국내 일별 체결내역"""

    __path__ = None

    account_number: KisAccountNumber
    """계좌번호"""

    orders: list[KisDailyOrder] = KisList(KisDomesticDailyOrder)["output1"]
    """일별 체결내역"""

    def __init__(self, account_number: KisAccountNumber):
        super().__init__()
        self.account_number = account_number

    def __post_init__(self) -> None:
        super().__post_init__()

        for order in self.orders:
            order.account_number = self.account_number

    def __kis_post_init__(self):
        super().__kis_post_init__()
        self._kis_spread(self.orders)


DOMESTIC_DAILY_ORDERS_API_CODES: dict[tuple[bool, bool], str] = {
    # (실전투자여부, 최근3개월이내여부) -> API코드
    (True, True): "TTTC8001R",
    (True, False): "CTSC9115R",
    (False, True): "VTTC8001R",
    (False, False): "VTSC9115R",
}


def _domestic_daily_orders(
    self: "PyKis",
    account: str | KisAccountNumber,
    start: date,
    end: date,
    type: ORDER_TYPE | None = None,
    page: KisPage | None = None,
    continuous: bool = True,
) -> KisDomesticDailyOrders:
    if not isinstance(account, KisAccountNumber):
        account = KisAccountNumber(account)

    if start > end:
        start, end = end, start

    now = datetime.now(TIMEZONE).date()

    is_recent = (now.year - start.year) * 12 - now.month <= 3

    if end.month + (now.year - end.year) * 12 - now.month > 3 and is_recent:
        raise ValueError("조회 기간은 최근 3개월 이내거나 3개월 이상이어야 합니다.")

    page = (page or KisPage.first()).to(100)
    first = None

    while True:
        result = self.fetch(
            "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            api=DOMESTIC_DAILY_ORDERS_API_CODES[(not self.virtual, is_recent)],
            params={
                "INQR_STRT_DT": start.strftime("%Y%m%d"),
                "INQR_END_DT": end.strftime("%Y%m%d"),
                "SLL_BUY_DVSN_CD": "00" if type is None else ("02" if type == "buy" else "01"),
                "INQR_DVSN": "00",
                "PDNO": "",
                "CCLD_DVSN": "00",
                "ORD_GNO_BRNO": "",
                "ODNO": "",
                "INQR_DVSN_3": "00",
                "INQR_DVSN_1": "",
            },
            form=[
                account,
                page,
            ],
            continuous=not page.is_first,
            response_type=KisDomesticDailyOrders(
                account_number=account,
            ),
        )

        if first is None:
            first = result
        else:
            first.orders.extend(result.orders)

        if not continuous or result.is_last:
            break

        page = result.next_page

    return first


def domestic_daily_orders(
    self: "PyKis",
    account: str | KisAccountNumber,
    start: date,
    end: date,
    type: ORDER_TYPE | None = None,
) -> KisDomesticDailyOrders:
    """
    한국투자증권 통합 체결내역 조회

    국내주식주문 -> 주식일별주문체결조회[v1_국내주식-005]
    (업데이트 날짜: 2024/04/02)

    Args:
        account (str | KisAccountNumber): 계좌번호
        page (KisPage, optional): 페이지 정보
        start (date): 조회 시작일
        end (date): 조회 종료일
        type (ORDER_TYPE, optional): 주문유형

    Raises:
        KisAPIError: API 호출에 실패한 경우
        ValueError: 계좌번호가 잘못된 경우
    """
    if start > end:
        start, end = end, start

    now = datetime.now(TIMEZONE).date()

    if (now.year - start.year) * 12 - now.month <= 3 and (now.year - end.year) * 12 - now.month <= 3:
        return _domestic_daily_orders(
            self,
            account=account,
            start=start,
            end=end,
            type=type,
        )

    split_start = now - timedelta(days=90)
    split_start = date(split_start.year, split_start.month, 1)

    first = _domestic_daily_orders(
        self,
        account=account,
        start=split_start,
        end=end,
        type=type,
    )

    first.orders.extend(
        _domestic_daily_orders(
            self,
            account=account,
            start=start,
            end=split_start - timedelta(days=1),
            type=type,
        ).orders
    )

    return first
