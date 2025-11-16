// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title Simple Flash Loan Arbitrage Contract
 * @notice Example contract showing how to compete with other arbitrageurs
 * @dev For educational purposes - add security checks before using with real funds
 */

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
}

interface IPancakePair {
    function token0() external view returns (address);
    function token1() external view returns (address);
    function getReserves() external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast);
    function swap(uint amount0Out, uint amount1Out, address to, bytes calldata data) external;
}

interface IPancakeFactory {
    function getPair(address tokenA, address tokenB) external view returns (address pair);
}

/**
 * @title FlashLoanArbitrage
 * @notice Executes arbitrage using PancakeSwap flash loans
 *
 * HOW IT WORKS:
 * 1. Detect imbalance in pool (off-chain bot)
 * 2. Call executeArbitrage() with competitive gas price
 * 3. Borrow tokens via flash loan (0 capital needed)
 * 4. Swap to rebalance pool and capture profit
 * 5. Repay flash loan + 0.09% fee
 * 6. Keep profit
 *
 * COMPETITION:
 * - Fastest transaction wins (highest gas price)
 * - Other competitors' TXs revert (opportunity only exists once)
 * - Can bid up to 50% of profit and still be profitable
 */
contract FlashLoanArbitrage {
    address public owner;
    address public pancakeFactory = 0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73;

    event ArbitrageExecuted(
        address indexed pool,
        address indexed token,
        uint256 borrowed,
        uint256 profit,
        uint256 gasPrice
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice Execute flash loan arbitrage on imbalanced pool
     * @param poolAddress The imbalanced pool to arbitrage
     * @param tokenToBorrow Which token to borrow (token0 or token1)
     * @param amountToBorrow How much to borrow (calculated off-chain)
     * @dev This function competes with other bots - highest gas price wins
     */
    function executeArbitrage(
        address poolAddress,
        address tokenToBorrow,
        uint256 amountToBorrow
    ) external onlyOwner {
        IPancakePair pool = IPancakePair(poolAddress);

        // Determine which token we're borrowing
        address token0 = pool.token0();
        address token1 = pool.token1();

        uint256 amount0Out = 0;
        uint256 amount1Out = 0;

        if (tokenToBorrow == token0) {
            amount0Out = amountToBorrow;
        } else {
            amount1Out = amountToBorrow;
        }

        // Initiate flash loan by calling swap with data
        // This will callback to pancakeCall() below
        bytes memory data = abi.encode(tokenToBorrow, amountToBorrow);
        pool.swap(amount0Out, amount1Out, address(this), data);
    }

    /**
     * @notice Callback function called by PancakeSwap during flash loan
     * @dev This is where the arbitrage logic executes
     */
    function pancakeCall(
        address sender,
        uint256 amount0,
        uint256 amount1,
        bytes calldata data
    ) external {
        // Decode flash loan parameters
        (address tokenBorrowed, uint256 amountBorrowed) = abi.decode(data, (address, uint256));

        // SECURITY: Verify caller is a legitimate PancakeSwap pair
        address token0 = IPancakePair(msg.sender).token0();
        address token1 = IPancakePair(msg.sender).token1();
        address pairAddress = IPancakeFactory(pancakeFactory).getPair(token0, token1);
        require(msg.sender == pairAddress, "Invalid pair");
        require(sender == address(this), "Invalid sender");

        // Record balance before arbitrage
        uint256 balanceBefore = IERC20(tokenBorrowed).balanceOf(address(this));

        // ============================================
        // ARBITRAGE LOGIC
        // ============================================
        // The borrowed tokens are now in this contract
        // Execute the profitable trade to rebalance the pool
        // This is where you would:
        // 1. Swap on the imbalanced pool to capture profit
        // 2. Or swap on another DEX and back
        // 3. Or execute multi-hop arbitrage
        //
        // For this example, we just demonstrate the flash loan mechanics
        // Real implementation would calculate optimal swap amounts off-chain
        // and execute the specific swaps needed
        // ============================================

        // Calculate repayment (borrowed + 0.09% fee)
        // PancakeSwap flash loan fee is 0.09% (9/10000)
        uint256 feeAmount = (amountBorrowed * 9) / 10000;
        uint256 amountToRepay = amountBorrowed + feeAmount;

        // Ensure we have enough to repay
        uint256 balanceAfter = IERC20(tokenBorrowed).balanceOf(address(this));
        require(balanceAfter >= amountToRepay, "Insufficient funds to repay");

        // Repay flash loan
        IERC20(tokenBorrowed).transfer(msg.sender, amountToRepay);

        // Calculate profit
        uint256 finalBalance = IERC20(tokenBorrowed).balanceOf(address(this));
        uint256 profit = finalBalance - (balanceBefore - amountBorrowed);

        emit ArbitrageExecuted(
            msg.sender,
            tokenBorrowed,
            amountBorrowed,
            profit,
            tx.gasprice
        );
    }

    /**
     * @notice Withdraw profits
     * @param token Token to withdraw
     */
    function withdrawProfit(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        require(balance > 0, "No balance");
        IERC20(token).transfer(owner, balance);
    }

    /**
     * @notice Emergency withdraw (if something goes wrong)
     */
    function emergencyWithdraw(address token, uint256 amount) external onlyOwner {
        IERC20(token).transfer(owner, amount);
    }

    /**
     * @notice Allow contract to receive BNB
     */
    receive() external payable {}
}

/**
 * USAGE EXAMPLE:
 *
 * 1. Deploy this contract to BSC
 * 2. Run monitoring bot to detect imbalances (see Python example)
 * 3. When imbalance detected, bot calls:
 *
 *    contract.executeArbitrage(
 *        poolAddress,
 *        tokenToBorrow,
 *        amountToBorrow,
 *        { gasPrice: competitiveGasPrice }  // Higher gas = higher priority
 *    )
 *
 * 4. Contract borrows tokens via flash loan (0 capital needed)
 * 5. Executes arbitrage swaps
 * 6. Repays loan + 0.09% fee
 * 7. Keeps profit
 *
 * COMPETITION:
 * - Multiple bots detect same opportunity
 * - All submit transactions to same block
 * - Transaction with HIGHEST GAS PRICE executes first
 * - Winner profits, all other TXs revert (opportunity gone)
 *
 * GAS PRICE STRATEGY:
 * - Small opportunity ($10K): Bid 10-50 Gwei
 * - Medium opportunity ($50K): Bid 50-500 Gwei
 * - Large opportunity ($100K+): Bid 500-5000 Gwei
 * - Maximum: Up to 50% of profit
 *
 * PROFIT CALCULATION:
 * - Gross: $50,000 (from rebalancing pool)
 * - Flash loan fee: $45 (0.09%)
 * - Gas cost: $12 (50 Gwei, 250K gas)
 * - Net profit: $49,943
 */
