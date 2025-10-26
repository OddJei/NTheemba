# Enhanced Phase 2 Architecture: Intent/Feature-Based Tree Selection

## 🎯 Overview

The enhanced Phase 2 implementation now supports **multiple tree structures per mode** by incorporating **intent/feature-based tree selection**. This allows for more granular and context-aware bot behavior.

## 🏗️ Architecture Components

### 1. **Tree Selector** (`utils/tree_selector.py`)
**Purpose**: Determines the correct tree structure based on session mode, user role, and intent/feature.

**Key Features**:
- **Mode Detection**: Identifies public vs registered mode
- **Role Detection**: Determines MSME, affiliate, customer, or staff role
- **Intent/Feature Extraction**: Maps resolved intents to specific features
- **Tree Mapping**: Maps mode+role+feature combinations to specific trees
- **Tree Switching**: Handles dynamic tree switching during sessions

**Tree Mapping Structure**:
```python
tree_mapping = {
    "public": {
        "catalog_browse": "public_catalog_tree",
        "order": "public_order_tree", 
        "registration": "public_registration_tree",
        "help": "public_help_tree"
    },
    "registered": {
        "msme": {
            "product_management": "msme_product_tree",
            "analytics_dashboard": "msme_analytics_tree",
            "profile_management": "msme_profile_tree",
            "order_management": "msme_order_tree"
        },
        "affiliate": {
            "catalog_browse": "affiliate_catalog_tree",
            "commission_tracking": "affiliate_commission_tree"
        }
    }
}
```

### 2. **Enhanced Tree Progression Service**
**New Capabilities**:
- **Tree Selection**: Automatically selects appropriate tree based on context
- **Tree Switching**: Detects when user switches between features and loads new tree
- **Session Continuity**: Maintains session state across tree switches
- **Intent-Based Routing**: Routes to correct nodes based on resolved intents

**Key Methods**:
- `select_and_load_tree()`: Selects and loads appropriate tree
- `check_tree_switch_needed()`: Detects if tree switch is required
- `progress_to_next_node()`: Enhanced with tree selection logic

### 3. **Enhanced Node Executor Service**
**New Capabilities**:
- **Feature-Based Handler Routing**: Routes to handlers based on mode+role+feature
- **Dynamic Handler Path Construction**: Builds handler paths dynamically
- **Intent-Aware Execution**: Considers intent/feature in handler selection

**Handler Path Structure**:
```
handlers.{mode}.{feature}.{handler_function}  # for public mode
handlers.{mode}.{role}.{feature}.{handler_function}  # for registered mode
```

**Examples**:
- `handlers.public_mode.catalog_browse.serve_categories`
- `handlers.public_mode.order.confirm_cart`
- `handlers.registered_mode.msme.product_management.add_product`
- `handlers.registered_mode.affiliate.commission_tracking.view_commission`

## 🔄 Tree Selection Flow

### 1. **Initial Tree Selection**
```
User Input → Intent Resolution → Feature Extraction → Tree Selection → Node Execution
```

### 2. **Tree Switching Flow**
```
Current Tree → New Intent → Feature Change → Tree Switch → New Node Execution
```

### 3. **Handler Routing Flow**
```
Node Execution → Mode+Role+Feature → Handler Path → Handler Execution → Response
```

## 📊 Intent/Feature Mapping

### **Public Mode Features**
- **catalog_browse**: Browse products, view categories, add to cart
- **order**: Place orders, checkout, payment processing
- **registration**: User registration, signup flows
- **help**: Support, assistance, FAQ

### **MSME Features**
- **product_management**: Add/edit/remove products
- **analytics_dashboard**: View sales analytics, reports
- **profile_management**: Update business profile
- **order_management**: Manage incoming orders

### **Affiliate Features**
- **catalog_browse**: Browse products for referral (includes link generation as subtree)
- **commission_tracking**: Track commissions, earnings


## 🎯 Benefits

### 1. **Granular Control**
- Each feature has its own dedicated tree structure
- Specific handlers for each feature within each mode/role
- Better organization and maintainability

### 2. **Context Awareness**
- Bot behavior adapts based on user intent and current feature
- Seamless switching between different workflows
- Maintains session context across feature switches

### 3. **Scalability**
- Easy to add new features and trees
- Modular handler organization
- Clear separation of concerns

### 4. **User Experience**
- More relevant responses based on current context
- Smooth transitions between different workflows
- Contextual help and guidance

## 🔧 Implementation Details

### **Tree Selection Logic**
1. Extract intent directly from payload (intent is the feature/tree name)
2. Determine session mode (public/registered)
3. Get user role (for registered mode: msme/affiliate only)
4. Map mode+role+feature to tree name
5. Load and validate tree
6. Update session with tree information

### **Handler Routing Logic**
1. Get session mode and user role
2. Extract intent/feature from payload
3. Construct handler path: `handlers.{mode}.{role}.{feature}.{function}`
4. Import and execute handler
5. Process and return results

### **Tree Switching Logic**
1. Check if current tree matches expected tree for new intent
2. If not, switch to appropriate tree
3. Reset to root node of new tree
4. Continue with normal progression

## 🚀 Usage Examples

### **Public User Browsing Catalog**
```
Intent: "browse_catalog" → Feature: "catalog_browse" → Tree: "public_catalog_tree"
Handler: handlers.public_mode.catalog_browse.serve_categories
```

### **Public User Placing Order**
```
Intent: "place_order" → Feature: "order" → Tree: "public_order_tree"
Handler: handlers.public_mode.order.confirm_cart
```

### **MSME Managing Products**
```
Intent: "add_product" → Feature: "product_management" → Tree: "msme_product_tree"
Handler: handlers.registered_mode.msme.product_management.add_product
```

### **Affiliate Tracking Commission**
```
Intent: "commission_tracking" → Feature: "commission_tracking" → Tree: "affiliate_commission_tree"
Handler: handlers.registered_mode.affiliate.commission_tracking.view_commission
```

## ✅ Enhanced Phase 2 Complete

The enhanced Phase 2 implementation now provides:
- **Intent/Feature-based tree selection**
- **Multiple tree structures per mode**
- **Dynamic tree switching**
- **Feature-specific handler routing**
- **Context-aware bot behavior**
- **Scalable architecture for future features**

This architecture supports the complex requirements of having different tree structures for different features within the same mode, providing a much more flexible and maintainable bot service.
