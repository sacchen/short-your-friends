from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

STEPS_REWARD_RATE = Decimal("0.01")  # Credits per step
DOOMSCROLL_TAX_RATE = Decimal("5.00")  # Credits burned per hour


@dataclass
class Account:
    user_id: str
    # Total equity = available + locked
    balance_available: Decimal = field(default_factory=lambda: Decimal("0.00"))
    balance_locked: Decimal = field(default_factory=lambda: Decimal("0.00"))  # Money in active buy orders

    # Track shares: Key=MarketID (eg "alice,480"), Value=Quantity
    portfolio: dict[str, int] = field(default_factory=dict)

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

    def confirm_trade(
        self,
        buyer_id: str,
        seller_id: str,
        market_id: str,
        price: Decimal,
        quantity: int,
    ) -> None:
        """
        Executes cash transfer
        Buyer: Locked funds are removed/spent.
        Seller: Funds are added to available balance.
        Only substracts locked cash from Buyer
        """
        cost = price * Decimal(quantity)

        # Buyer: Pays Cash, Gets Shares
        # funds were already locked, so we take money out of Locked
        buyer = self.get_account(buyer_id)
        buyer.balance_locked -= cost
        # TODO: In database, assert >0

        # Make sure balances don't go negative.
        if buyer.balance_locked < Decimal("0.00"):
            print(f"CRITICAL: Buyer {buyer_id} had negative locked balance! Resetting.")
            buyer.balance_locked = Decimal("0.00")

        # Add shares to buyer portfolio
        current_qty = buyer.portfolio.get(market_id, 0)
        buyer.portfolio[market_id] = current_qty + quantity

        # Seller: Gets Cash, Loses Shares
        # They never locked cash, so we just add to "Available"
        seller = self.get_account(seller_id)
        seller.balance_available += cost

        # Remove shares from seller portfolio
        # Negative means they are Short
        current_qty = seller.portfolio.get(market_id, 0)
        seller.portfolio[market_id] = current_qty - quantity

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
                "portfolio": acc.portfolio,  # This is Dict[str, int], not str
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
            # Portfolio can be dict or missing
            portfolio_data = balances.get("portfolio", {})
            if isinstance(portfolio_data, dict):
                acc.portfolio = portfolio_data
            else:
                acc.portfolio = {}
            self.accounts[user_id] = acc
