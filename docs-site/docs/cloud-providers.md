---
sidebar_position: 3
---

# Connecting Cloud Accounts

CIS connects to your cloud accounts to discover and manage compute instances. You add accounts through **Settings > Cloud Accounts** — just pick a provider, paste your credentials, and sync.

![Settings - Cloud Accounts](/img/screenshots/settings-cloud-accounts.png)

CIS supports three providers:

- **AWS** — EC2 instances
- **Azure** — Virtual Machines (with full deallocation to stop billing)
- **GCP** — Compute Engine instances

## AWS

### Creating access in AWS

1. Open the [IAM Console](https://console.aws.amazon.com/iam/) and go to **Users > Create user**
2. Enter a name like `cis-scheduler` and click **Next**
3. Select **Attach policies directly**, then click **Create policy**
4. Switch to the **JSON** tab and paste the policy below
5. Name the policy (e.g., `CIS-EC2-Scheduler`) and create it
6. Back on the user creation page, search for and attach your new policy
7. Complete the user creation, then go to **Security credentials > Create access key**
8. Select **Third-party service**, acknowledge, and create the key
9. Copy the **Access key ID** and **Secret access key** — you'll need both in CIS

### Minimum IAM policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "ec2:DescribeRegions",
        "ec2:DescribeInstances",
        "ec2:StartInstances",
        "ec2:StopInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

To restrict further, you can scope `ec2:StartInstances` and `ec2:StopInstances` to specific resource ARNs or tag-based conditions.

### What to enter in CIS

| Field | Description |
|---|---|
| **Access Key ID** | The access key from the IAM user |
| **Secret Access Key** | The secret key (stored encrypted) |

## Azure

### Creating access in Azure

1. Open the [Azure Portal](https://portal.azure.com) and go to **Microsoft Entra ID > App registrations > New registration**
2. Enter a name like `cis-scheduler`, leave the defaults, and click **Register**
3. On the app's overview page, copy the **Application (client) ID** and **Directory (tenant) ID**
4. Go to **Certificates & secrets > New client secret**, add a description, and create it
5. Copy the secret **Value** immediately (it won't be shown again)
6. Now go to **Subscriptions**, select the subscription you want CIS to manage
7. Go to **Access control (IAM) > Add role assignment**
8. Search for and select the **Virtual Machine Contributor** role, click **Next**
9. Select **User, group, or service principal**, click **Select members**, find your app registration, and assign

If you prefer a more restrictive custom role, the minimum permissions are:

- `Microsoft.Compute/virtualMachines/read`
- `Microsoft.Compute/virtualMachines/instanceView/read`
- `Microsoft.Compute/virtualMachines/start/action`
- `Microsoft.Compute/virtualMachines/deallocate/action`

### What to enter in CIS

| Field | Description |
|---|---|
| **Subscription ID** | The Azure subscription to manage |
| **Tenant ID** | Your Microsoft Entra directory ID |
| **Client ID** | The application (client) ID from the app registration |
| **Client Secret** | The client secret value (stored encrypted) |

:::note
CIS uses **deallocate** (not power-off) when stopping Azure VMs. This fully releases compute resources and stops billing, which is what you want for cost savings.
:::

## GCP

### Creating access in GCP

1. Open the [GCP Console](https://console.cloud.google.com) and go to **IAM & Admin > Service Accounts**
2. Click **Create Service Account**
3. Enter a name like `cis-scheduler` and click **Create and continue**
4. Grant the role **Compute Instance Admin (v1)** (`roles/compute.instanceAdmin.v1`) and click **Continue**
5. Click **Done** to finish creating the service account
6. Click on the new service account, go to the **Keys** tab
7. Click **Add Key > Create new key**, select **JSON**, and click **Create**
8. Save the downloaded JSON file — you'll paste its contents into CIS

If you prefer a custom role with fewer permissions, the minimum is:

- `compute.instances.list`
- `compute.instances.get`
- `compute.instances.start`
- `compute.instances.stop`

### What to enter in CIS

| Field | Description |
|---|---|
| **Project ID** | The GCP project ID |
| **Service Account JSON** | The full contents of the JSON key file (stored encrypted) |

:::note
GCP organizes instances by **zone** (e.g., `us-east1-b`), not by region. CIS discovers instances across all zones in the project automatically.
:::

## Adding an account in CIS

1. Go to **Settings > Cloud Accounts**
2. Click **Add Account**
3. Choose the provider (AWS, Azure, or GCP)
4. Enter a descriptive name and paste your credentials
5. Optionally select specific regions — by default, CIS scans all available regions
6. Click **Save**

CIS validates your credentials on save. If the connection fails, double-check your credentials and permissions.

## Syncing resources

After adding an account, click **Sync** to discover your cloud instances. CIS will scan the selected regions and import all compute instances it finds. Discovered resources appear on the **Resources** page, where you can see their current state, provider, region, and instance type.

You can re-sync at any time to pick up new instances or reflect changes made directly in the cloud console.
