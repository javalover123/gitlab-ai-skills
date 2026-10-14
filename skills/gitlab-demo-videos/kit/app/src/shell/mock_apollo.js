// A tiny in-browser GraphQL "server": resolves operations by operationName with synthetic data.
// Used instead of GitLab's HTTP Apollo link so pages run fully offline.
//
//   const client = createMockApolloClient({
//     getCreditCaps: (variables, operation) => ({ subscriptionUsage: { __typename: '...', ... } }),
//     upsertFlatUserCap: async (vars) => { state.cap = vars.input.cap; return { upsertFlatUserCap: { errors: [] } }; },
//   }, { latency: 450 });            // latency: ms | (operation) => ms | { operationName: ms, default: ms }
//   new Vue({ apolloProvider: new VueApollo({ defaultClient: client }), ... })
//
// Resolvers may return a Promise. Throwing `new MockGraphQLError('msg')` answers { errors: [{ message }] }.
// Include __typename on objects when the real query uses fragments on interfaces/unions.
// Unresolved operations are logged as `[mock-apollo] no resolver for X` (see harness/shot.mjs output).
// For components that use GitLab's DEFAULT client (~/lib/graphql createDefaultClient, e.g. the sidebar),
// answer server-side instead: app/demos/<slug>/graphql.mjs (see harness/serve.mjs).
import { ApolloClient, InMemoryCache, ApolloLink, Observable } from '@apollo/client/core';
import possibleTypes from '~/graphql_shared/possible_types.json';

export class MockGraphQLError extends Error {}

const delayFor = (latency, operation) => {
  if (typeof latency === 'function') return latency(operation);
  if (latency && typeof latency === 'object') return latency[operation.operationName] ?? latency.default ?? 450;
  return latency;
};

export function createMockLink(resolvers, { latency = 450 } = {}) {
  return new ApolloLink(
    (operation) =>
      new Observable((observer) => {
        const resolver = resolvers[operation.operationName];
        const timer = setTimeout(async () => {
          try {
            if (!resolver) {
              // eslint-disable-next-line no-console
              console.warn('[mock-apollo] no resolver for', operation.operationName);
              observer.next({ data: null });
            } else {
              observer.next({ data: await resolver(operation.variables, operation) });
            }
            observer.complete();
          } catch (e) {
            if (e instanceof MockGraphQLError) {
              observer.next({ data: null, errors: [{ message: e.message }] });
              observer.complete();
            } else {
              // eslint-disable-next-line no-console
              console.error('[mock-apollo] resolver failed for', operation.operationName, e);
              observer.error(e);
            }
          }
        }, delayFor(latency, operation));
        return () => clearTimeout(timer);
      }),
  );
}

export function createMockApolloClient(resolvers, { latency = 450, cacheConfig = {} } = {}) {
  return new ApolloClient({
    link: createMockLink(resolvers, { latency }),
    cache: new InMemoryCache({ possibleTypes, ...cacheConfig }),
  });
}
