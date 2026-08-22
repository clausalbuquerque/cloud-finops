import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ClientSecretCredential, DefaultAzureCredential, TokenCredential } from '@azure/identity';
import { ResourceManagementClient, GenericResourceExpanded } from '@azure/arm-resources';
import { DiscoveredResource, ResourceDiscoveryParams, ResourceSku } from './interfaces';

/**
 * Service for discovering and listing Azure resources via Azure Resource Manager.
 *
 * Uses the @azure/arm-resources SDK to list resources by subscription,
 * with optional filtering by resource type, resource group, and tags.
 */
@Injectable()
export class AzureResourceClientService {
  private readonly logger = new Logger(AzureResourceClientService.name);
  private readonly client: ResourceManagementClient;
  private readonly defaultSubscriptionId: string;

  constructor(private readonly configService: ConfigService) {
    const tenantId = this.configService.get<string>('azure.tenantId', '');
    const clientId = this.configService.get<string>('azure.clientId', '');
    const clientSecret = this.configService.get<string>('azure.clientSecret', '');
    this.defaultSubscriptionId = this.configService.get<string>('azure.subscriptionId', '');

    const credential = this.createCredential(tenantId, clientId, clientSecret);
    this.client = new ResourceManagementClient(credential, this.defaultSubscriptionId);

    this.logger.log('AzureResourceClientService initialized');
  }

  /**
   * Discover Azure resources matching the given parameters.
   *
   * @param params - Discovery parameters (subscription, resource type, resource group, tags)
   * @returns Array of discovered resources
   */
  async discoverResources(params: ResourceDiscoveryParams = {}): Promise<DiscoveredResource[]> {
    const subscriptionId = params.subscriptionId || this.defaultSubscriptionId;

    if (!subscriptionId) {
      throw new Error('No subscription ID provided and no default configured');
    }

    this.logger.log(
      `Discovering resources in subscription ${subscriptionId}` +
        `${params.resourceType ? ` (type: ${params.resourceType})` : ''}` +
        `${params.resourceGroup ? ` (rg: ${params.resourceGroup})` : ''}`,
    );

    const filter = this.buildFilter(params);
    const resources: DiscoveredResource[] = [];

    try {
      const iterator = params.resourceGroup
        ? this.client.resources.listByResourceGroup(params.resourceGroup, {
            filter: filter || undefined,
          })
        : this.client.resources.list({ filter: filter || undefined });

      for await (const resource of iterator) {
        const mapped = this.mapResource(resource);
        if (mapped) {
          resources.push(mapped);
        }
      }

      this.logger.log(`Discovered ${resources.length} resources`);
      return resources;
    } catch (error: unknown) {
      this.handleError(error, 'discovering resources');
      throw error;
    }
  }

  /**
   * Get a list of distinct resource types present in the subscription.
   *
   * @param subscriptionId - Optional subscription ID override
   * @returns Array of resource type strings
   */
  async listResourceTypes(subscriptionId?: string): Promise<string[]> {
    const resources = await this.discoverResources({
      subscriptionId: subscriptionId || this.defaultSubscriptionId,
    });

    const types = new Set(resources.map((r) => r.type));
    return [...types].sort();
  }

  /**
   * Build an OData filter string from discovery parameters.
   */
  private buildFilter(params: ResourceDiscoveryParams): string | null {
    const filters: string[] = [];

    if (params.resourceType) {
      filters.push(`resourceType eq '${params.resourceType}'`);
    }

    return filters.length > 0 ? filters.join(' and ') : null;
  }

  /**
   * Map an Azure ARM resource to our DiscoveredResource interface.
   */
  mapResource(resource: GenericResourceExpanded): DiscoveredResource | null {
    if (!resource.id || !resource.name || !resource.type) {
      return null;
    }

    // Extract resource group from the resource ID
    const rgMatch = resource.id.match(/\/resourceGroups\/([^/]+)/i);
    const resourceGroup = rgMatch ? rgMatch[1] : 'unknown';

    let sku: ResourceSku | undefined;
    if (resource.sku) {
      sku = {
        name: resource.sku.name,
        tier: resource.sku.tier,
        capacity: resource.sku.capacity,
      };
    }

    return {
      id: resource.id,
      name: resource.name,
      type: resource.type,
      resourceGroup,
      location: resource.location || 'unknown',
      sku,
      tags: resource.tags as Record<string, string> | undefined,
    };
  }

  /**
   * Create an Azure credential based on available configuration.
   */
  private createCredential(
    tenantId: string,
    clientId: string,
    clientSecret: string,
  ): TokenCredential {
    if (tenantId && clientId && clientSecret) {
      this.logger.log('Using ClientSecretCredential for authentication');
      return new ClientSecretCredential(tenantId, clientId, clientSecret);
    }

    this.logger.log('Using DefaultAzureCredential for authentication');
    return new DefaultAzureCredential();
  }

  /**
   * Log meaningful error details.
   */
  private handleError(error: unknown, context: string): void {
    const statusCode = this.extractStatusCode(error);
    const message = error instanceof Error ? error.message : String(error);

    if (statusCode === 401 || statusCode === 403) {
      this.logger.error(
        `Authentication/authorization failed while ${context} (${statusCode}): ${message}`,
      );
    } else if (statusCode === 429) {
      this.logger.error(`Rate limit exceeded while ${context}: ${message}`);
    } else {
      this.logger.error(`Error while ${context}: ${message}`);
    }
  }

  /**
   * Extract HTTP status code from an error.
   */
  private extractStatusCode(error: unknown): number | undefined {
    if (error && typeof error === 'object' && 'statusCode' in error) {
      return (error as { statusCode: number }).statusCode;
    }
    return undefined;
  }
}
