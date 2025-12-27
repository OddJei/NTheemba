# NTheemba Project

## Architecture

- [docs/bot-layer-architecture.md](docs/bot-layer-architecture.md)

## For Contributors

### Getting Started

1. **Clone the Repository**

   ```bash
   git clone https://github.com/OddJei/NTheemba.git
   cd NTheemba
   ```

### Working on a Specific Service

1. **Before Starting Work**

   ```bash
   # Make sure you have the latest changes
   git pull origin master

   # Create a new branch for your service
   # Replace {service-name} with your assigned service (e.g., analytics, auth, etc.)
   git checkout -b feature/{service-name}
   ```

2. **Finding Your Service Design**

   - All service designs are located in `services/api-services/`
   - Each service has its own directory with a design file
   - Example locations:
     - Analytics Service: `services/api-services/analytics-service/analytics-service design.txt`
     - Auth Service: `services/api-services/auth-service/AuthService_design.txt`
     - Message Service: `services/api-services/messages-service/message-service design.txt`

3. **Making Changes**

   ```bash
   # Check which files you've modified
   git status

   # Stage your changes (replace {path} with the actual file path)
   git add services/api-services/{service-name}/{file-name}

   # Commit your changes with a descriptive message
   git commit -m "service: description of your changes"
   ```

4. **Pushing Your Changes**

   ```bash
   # Push your feature branch
   git push origin feature/{service-name}
   ```

5. **Creating a Pull Request**

   - Go to <https://github.com/OddJei/NTheemba/pull/new/feature/{service-name}>
   - Create a pull request from your feature branch to master
   - Add a description of your changes
   - Request review from project maintainers

### Working with Specific Files

To pull specific files without getting the entire repository:

```bash
# First time setup (if you haven't cloned the repo)
git init
git remote add origin https://github.com/OddJei/NTheemba.git

# Create a sparse checkout
git config core.sparseCheckout true

# Specify which service directory you want
echo "services/api-services/{service-name}/*" >> .git/info/sparse-checkout

# Pull only that directory
git pull origin master
```

### Available Services

Services are located in `services/api-services/`. Here are the main services:

1. Affiliate Services:
   - affiliate-event-service
   - affiliate-multiplier-service
   - affiliate-pool-service
   - affiliate-service

2. Core Services:
   - auth-service
   - business-service
   - catalog-inventory-service
   - delivery-service

3. User Interaction Services:
   - messages-service
   - notification-service
   - user-bot-event-service
   - user-bot-session-service

4. Business Logic Services:
   - cart-service
   - order-service
   - payment-service
   - subscription-service

5. Analytics & Search:
   - analytics-service
   - index-search-service

Each service directory contains its design document and implementation details.

### Best Practices

1. **Always create a new branch for your work**

   ```bash
   git checkout -b feature/{service-name}
   ```

2. **Keep commits focused and descriptive**

   ```bash
   git commit -m "service: what changed - why it changed"
   ```

3. **Update your branch regularly**

   ```bash
   git fetch origin
   git rebase origin/master
   ```

4. **Test your changes before pushing**

5. **Keep changes focused on your assigned service**

### Need Help?

If you need assistance or have questions:

1. Check the service design document in your service's directory

2. Review related services' design documents for integration points

3. Contact the project maintainers
If you want this distributed as a single `PORT_ASSIGNMENTS.md` in the repo or want the assignments added to each service README, tell me and I will add them automatically.

### Repository Structure

```text
services/
└── api-services/
    ├── affiliate-event-service/
    ├── affiliate-multiplier-service/
    ├── affiliate-pool-service/
    ├── affiliate-service/
    ├── analytics-service/
    ├── auth-service/
    ├── business-service/
    ├── cart-service/
    ├── catalog-inventory-service/
    ├── delivery-service/
    ├── index-search-service/
    ├── messages-service/
    ├── notification-service/
    ├── order-service/
    ├── payment-service/
    ├── subscription-service/
    ├── user-bot-event-service/
    └── user-bot-session-service/
```
