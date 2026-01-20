from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

STEPS_REWARD_RATE = Decimal("0.01")  # Credits per step
DOOMSCROLL_TAX_RATE = Decimal("5.00")  # Credits burned per hour


@dataclass
class Position:
    quantity: int = 0
    # Cost Basis
    # Average entry price in dollars/cents (Decimal for precision)
    average_entry_price: Decimal = field(default_factory=lambda: Decimal("0.00"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity": self.quantity,
            "average_entry_price": str(self.average_entry_price),
        }


@dataclass
class Account:
    user_id: str
    # Total equity = available + locked
    balance_available: Decimal = field(default_factory=lambda: Decimal("0.00"))
    balance_locked: Decimal = field(default_factory=lambda: Decimal("0.00"))  # Money in active buy orders

    # Track shares: Key=MarketID (eg "alice,480"), Value=Quantity
    portfolio: dict[str, Position] = field(default_factory=dict)

    def total_equity(self) -> Decimal:
        # result: Decimal = self.balance_available + self.balance_locked
        return self.balance_available + self.balance_locked


class EconomyManager:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}

    def get_account(self, user_id: str) -> Account:
        if user_id not in self.accounts:
            self.accounts[user_id] = Account(user_id=user_id)
        return self.accounts[user_id]

    def deposit(self, user_id: str, amount: Decimal) -> None:
        """Deposit credits to a user's available balance (for testing/admin)."""
        account = self.get_account(user_id)
        account.balance_available += amount

    # Game Mechanics (Mint/Burn)

    def process_proof_of_walk(self, user_id: str, steps: int) -> Decimal:
        """
        Mints new credits based on walking.
        Returns the amount minted.
        """
        account = self.get_account(user_id)
        reward = Decimal(steps) * STEPS_REWARD_RATE
        account.balance_available += reward
        return reward
        # print(f"User {user_id} walked {steps} steps. Minted {reward} credits.")

    def process_doomscroll_burn(self, user_id: str, minutes: int) -> Decimal:
        """
        Burns credits based on screen time.
        Returns the amount burned.
        """
        account = self.get_account(user_id)
        # Calculate tax: (minutes / 60) * hourly_rate
        tax = (Decimal(minutes) / Decimal(60)) * DOOMSCROLL_TAX_RATE

        tax = tax.quantize(Decimal("0.01"))  # Rounds to 2 decimal places.

        # No debt: Floor at zero.
        if account.balance_available >= tax:
            account.balance_available -= tax
        else:
            tax = account.balance_available  # Burned amount is whatever was left
            account.balance_available = Decimal("0.00")
            # Can trigger Bankrupt state in future

        # print(f"User {user_id} doomscrolled {minutes} mins. Burned {tax} credits.")
        return tax

    # Trading logic

    def attempt_order_lock(self, user_id: str, price: Decimal, quantity: int) -> bool:
        """
        Called before a buy order is sent to matching engine.
        Sellers do not lock cash (they lock shares), so this is only for buyers.
        Returns True if funds were successfully locked.
        """
        account = self.get_account(user_id)
        cost = price * Decimal(quantity)

        if account.balance_available >= cost:
            account.balance_available -= cost
            account.balance_locked += cost
            return True
        return False

    def release_order_lock(self, user_id: str, price: Decimal, quantity: int) -> None:
        """
        Called if a buy order is cancelled or expires.
        Returns funds from locked to available.
        """
        account = self.get_account(user_id)
        cost = price * Decimal(quantity)

        # Prevent negative locked balance
        if account.balance_locked >= cost:
            account.balance_locked -= cost
            account.balance_available += cost

    def _update_position(self, user_id: str, market_id: str, change_qty: int, price: Decimal) -> None:
        """
        Calculates new Weighted Average Price and updates portfolio.
        Handles: Opening, Increasing, Decreasing (Realizing P&L), and Flipping positions.
        """
        account = self.get_account(user_id)

        # Get existing position or create new empty one
        if market_id not in account.portfolio:
            account.portfolio[market_id] = Position()

        pos = account.portfolio[market_id]
        current_qty = pos.quantity
        current_avg = pos.average_entry_price

        new_qty = current_qty + change_qty

        # Scenario 1: Closing to 0 (Flat)
        if new_qty == 0:
            pos.quantity = 0
            pos.average_entry_price = Decimal("0.00")

        # Scenario 2: Opening new position (from 0)
        if current_qty == 0:
            pos.quantity = new_qty
            pos.average_entry_price = price
            return

        # Check direction
        is_same_direction = (current_qty > 0 and change_qty > 0) or (current_qty < 0 and change_qty < 0)

        # Scenario 3: Increasing Position (Averaging In)
        # Cost basis needs to be updated.
        if is_same_direction:
            # Weighted Average Formula: (OldVal + NewVal) / TotalQty
            total_val = (Decimal(abs(current_qty)) * current_avg) + (Decimal(abs(change_qty)) * price)
            total_qty = Decimal(abs(new_qty))
            pos.average_entry_price = total_val / total_qty
            pos.quantity = new_qty
            return

        # Scenario 4: Decreasing Position (Partial Close)
        # Reducing exposure, so cost basis does not change.
        # Realizing P&L on portion sold
        is_partial_close = abs(new_qty) < abs(current_qty)

        if is_partial_close:
            pos.quantity = new_qty
            # avg_entry_price stays the same
            return

        # Scneario 5: Flipping Position (Long to Short or Short to Long)
        # This closes old position and opens a new one with remainder.
        pos.quantity = new_qty
        pos.average_entry_price = price

    def confirm_trade(
        self,
        buyer_id: str,
        seller_id: str,
        market_id: str,
        price: Decimal,
        quantity: int,
    ) -> None:
        """
        Executes cash transfer and updates portfolio positions.
        Buyer: Locked funds are removed/spent.
        Seller: Funds are added to available balance.
        Only substracts locked cash from Buyer
        """
        cost = price * Decimal(quantity)

        # -- 1: Handle Cash Logic --

        # Buyer: Pays Cash (from Locked)
        buyer = self.get_account(buyer_id)
        buyer.balance_locked -= cost
        # TODO: In database, assert >0

        # Make sure balances don't go negative.
        if buyer.balance_locked < Decimal("0.00"):
            print(f"CRITICAL: Buyer {buyer_id} had negative locked balance! Resetting.")
            buyer.balance_locked = Decimal("0.00")

        # Seller: Gets Cash (to Available)
        seller = self.get_account(seller_id)
        seller.balance_available += cost

        # -- 2: Handle Portfolio/Position Logic --

        # Buyer: Adds +Quantity
        self._update_position(buyer_id, market_id, quantity, price)

        # Seller: Adds -Quantity (Shorts)
        self._update_position(seller_id, market_id, -quantity, price)

    def distribute_ubi(self, amount: Decimal = Decimal("100.00")) -> None:
        """Give everyone their daily bread."""
        for user_id in self.accounts:
            self.accounts[user_id].balance_available += amount
        # TODO: need database/timestamp log of last distribution
        # so function doesn't run every time server restarts

    # save to JSON for Persistence
    def dump_state(self) -> dict[str, dict[str, Any]]:
        """Export all accounts to dictionary."""
        return {
            user_id: {
                "available": str(acc.balance_available),
                "locked": str(acc.balance_locked),
                "portfolio": {
                    mid: pos.to_dict() for mid, pos in acc.portfolio.items()
                },  # This is Dict[str, int], not str
            }
            for user_id, acc in self.accounts.items()  # keys, values
            # acc is the Value (`Account` object)
        }

    def load_state(self, data: dict[str, dict[str, Any]]) -> None:
        """Restore accounts from dictionary."""
        self.accounts.clear()
        for user_id, balances in data.items():
            acc = Account(user_id=user_id)
            acc.balance_available = Decimal(balances["available"])
            acc.balance_locked = Decimal(balances["locked"])

            # Load Portfolio with Migration Path
            portfolio_data = balances.get("portfolio", {})
            acc.portfolio = {}

            for mid, pos_data in portfolio_data.items():
                if isinstance(pos_data, dict):
                    # Using PositionData format
                    p = Position(
                        quantity=int(pos_data.get("quantity", 0)),
                        average_entry_price=Decimal(pos_data.get("average_entry_price", "0.00")),
                    )
                    acc.portfolio[mid] = p
                else:
                    # Backward compatibility for old format (int)
                    # Assume entry price is 0 if migrating
                    p = Position(quantity=int(pos_data), average_entry_price=Decimal("0.00"))
                    acc.portfolio[mid] = p

            self.accounts[user_id] = acc
