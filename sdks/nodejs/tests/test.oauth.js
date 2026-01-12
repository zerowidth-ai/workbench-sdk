import assert from "assert";
import { isOAuthKey, parseExpiresAt, isTokenExpired, OAuthRefreshManager } from "../src/utilities/oauth.js";

/**
 * Unit tests for OAuth utility functions
 */

describe("OAuth Utilities", () => {
  describe("isOAuthKey", () => {
    it("should identify valid OAuth keys", () => {
      const validKey = {
        accessToken: "test-token",
        onRefresh: async () => ({ accessToken: "new-token" })
      };
      assert.strictEqual(isOAuthKey(validKey), true);
    });

    it("should reject invalid OAuth keys", () => {
      assert.strictEqual(isOAuthKey(null), false);
      assert.strictEqual(isOAuthKey(undefined), false);
      assert.strictEqual(isOAuthKey("string-key"), false);
      assert.strictEqual(isOAuthKey({ accessToken: "token" }), false); // Missing onRefresh
      assert.strictEqual(isOAuthKey({ onRefresh: () => {} }), false); // Missing accessToken
    });
  });

  describe("parseExpiresAt", () => {
    it("should parse epoch milliseconds", () => {
      const epoch = 1640995200000; // 2022-01-01 00:00:00 UTC
      assert.strictEqual(parseExpiresAt(epoch), epoch);
    });

    it("should parse ISO string", () => {
      const iso = "2022-01-01T00:00:00.000Z";
      const expected = new Date(iso).getTime();
      assert.strictEqual(parseExpiresAt(iso), expected);
    });

    it("should return null for invalid values", () => {
      assert.strictEqual(parseExpiresAt(null), null);
      assert.strictEqual(parseExpiresAt(undefined), null);
      assert.strictEqual(parseExpiresAt("invalid-date"), null);
    });
  });

  describe("isTokenExpired", () => {
    it("should detect expired tokens", () => {
      const expiredToken = {
        accessToken: "token",
        expiresAt: Date.now() - 10000, // Expired 10 seconds ago
        onRefresh: async () => ({ accessToken: "new-token" })
      };
      assert.strictEqual(isTokenExpired(expiredToken, 0), true);
    });

    it("should detect tokens expiring soon", () => {
      const soonToExpire = {
        accessToken: "token",
        expiresAt: Date.now() + 30000, // Expires in 30 seconds
        onRefresh: async () => ({ accessToken: "new-token" })
      };
      assert.strictEqual(isTokenExpired(soonToExpire, 60000), true); // 60s skew should catch it
    });

    it("should detect valid tokens", () => {
      const validToken = {
        accessToken: "token",
        expiresAt: Date.now() + 3600000, // Expires in 1 hour
        onRefresh: async () => ({ accessToken: "new-token" })
      };
      assert.strictEqual(isTokenExpired(validToken, 0), false);
    });

    it("should handle tokens without expiry", () => {
      const noExpiry = {
        accessToken: "token",
        onRefresh: async () => ({ accessToken: "new-token" })
      };
      assert.strictEqual(isTokenExpired(noExpiry, 0), false);
    });
  });

  describe("OAuthRefreshManager", () => {
    it("should refresh expired tokens", async () => {
      let refreshCallCount = 0;
      const oauthKey = {
        accessToken: "old-token",
        expiresAt: Date.now() - 10000, // Expired
        refreshToken: "refresh-token",
        onRefresh: async (context) => {
          refreshCallCount++;
          return {
            accessToken: "new-token",
            refreshToken: "refresh-token",
            expiresAt: Date.now() + 3600000
          };
        }
      };

      const manager = new OAuthRefreshManager({
        oauthExpirySkewMs: 0,
        oauthMaxRefreshRetries: 1,
        oauthRefreshTimeoutMs: 5000,
        keys: { test: oauthKey }
      });

      const updated = await manager.ensureValidToken("test", oauthKey);
      assert.strictEqual(refreshCallCount, 1);
      assert.strictEqual(updated.accessToken, "new-token");
    });

    it("should not refresh valid tokens", async () => {
      let refreshCallCount = 0;
      const oauthKey = {
        accessToken: "valid-token",
        expiresAt: Date.now() + 3600000, // Valid for 1 hour
        onRefresh: async () => {
          refreshCallCount++;
          return { accessToken: "new-token" };
        }
      };

      const manager = new OAuthRefreshManager({
        oauthExpirySkewMs: 0
      });

      const result = await manager.ensureValidToken("test", oauthKey);
      assert.strictEqual(refreshCallCount, 0);
      assert.strictEqual(result.accessToken, "valid-token");
    });

    it("should coalesce concurrent refresh requests", async () => {
      let refreshCallCount = 0;
      const oauthKey = {
        accessToken: "old-token",
        expiresAt: Date.now() - 10000,
        onRefresh: async () => {
          await new Promise(resolve => setTimeout(resolve, 100));
          refreshCallCount++;
          return {
            accessToken: "new-token",
            expiresAt: Date.now() + 3600000
          };
        }
      };

      const manager = new OAuthRefreshManager({
        oauthExpirySkewMs: 0,
        oauthMaxRefreshRetries: 1,
        oauthRefreshTimeoutMs: 5000
      });

      // Trigger multiple concurrent refreshes
      const promises = [
        manager.refreshToken("test", oauthKey),
        manager.refreshToken("test", oauthKey),
        manager.refreshToken("test", oauthKey)
      ];

      const results = await Promise.all(promises);
      
      // Should only call onRefresh once due to coalescing
      assert.strictEqual(refreshCallCount, 1);
      
      // All should return the same refreshed token
      results.forEach(result => {
        assert.strictEqual(result.accessToken, "new-token");
      });
    });

    it("should retry on refresh failure", async () => {
      let refreshCallCount = 0;
      const oauthKey = {
        accessToken: "old-token",
        expiresAt: Date.now() - 10000,
        onRefresh: async () => {
          refreshCallCount++;
          if (refreshCallCount < 2) {
            throw new Error("Temporary failure");
          }
          return {
            accessToken: "new-token",
            expiresAt: Date.now() + 3600000
          };
        }
      };

      const manager = new OAuthRefreshManager({
        oauthExpirySkewMs: 0,
        oauthMaxRefreshRetries: 3,
        oauthRefreshTimeoutMs: 5000
      });

      const result = await manager.refreshToken("test", oauthKey);
      assert.strictEqual(refreshCallCount, 2);
      assert.strictEqual(result.accessToken, "new-token");
    });

    it("should throw after max retries", async () => {
      const oauthKey = {
        accessToken: "old-token",
        expiresAt: Date.now() - 10000,
        onRefresh: async () => {
          throw new Error("Persistent failure");
        }
      };

      const manager = new OAuthRefreshManager({
        oauthExpirySkewMs: 0,
        oauthMaxRefreshRetries: 2,
        oauthRefreshTimeoutMs: 5000
      });

      try {
        await manager.refreshToken("test", oauthKey);
        assert.fail("Should have thrown an error");
      } catch (error) {
        assert(error.message.includes("OAuth refresh failed"));
        assert(error.message.includes("3 retries")); // Initial + 2 retries
      }
    });

    it("should timeout refresh callbacks", async () => {
      const oauthKey = {
        accessToken: "old-token",
        expiresAt: Date.now() - 10000,
        onRefresh: async () => {
          await new Promise(resolve => setTimeout(resolve, 10000)); // 10 second delay
          return { accessToken: "new-token" };
        }
      };

      const manager = new OAuthRefreshManager({
        oauthExpirySkewMs: 0,
        oauthMaxRefreshRetries: 1,
        oauthRefreshTimeoutMs: 100 // 100ms timeout
      });

      try {
        await manager.refreshToken("test", oauthKey);
        assert.fail("Should have thrown a timeout error");
      } catch (error) {
        assert(error.message.includes("timeout"));
      }
    });

    it("should update in-memory keys after refresh", async () => {
      const keys = {
        test: {
          accessToken: "old-token",
          expiresAt: Date.now() - 10000,
          onRefresh: async () => ({
            accessToken: "new-token",
            expiresAt: Date.now() + 3600000
          })
        }
      };

      const manager = new OAuthRefreshManager({
        oauthExpirySkewMs: 0,
        oauthMaxRefreshRetries: 1,
        oauthRefreshTimeoutMs: 5000,
        keys: keys
      });

      await manager.refreshToken("test", keys.test);
      
      // Key should be updated in memory
      assert.strictEqual(keys.test.accessToken, "new-token");
    });

    it("should emit refresh events", async () => {
      const events = [];
      const oauthKey = {
        accessToken: "old-token",
        expiresAt: Date.now() - 10000,
        onRefresh: async () => ({
          accessToken: "new-token",
          expiresAt: Date.now() + 3600000
        })
      };

      const manager = new OAuthRefreshManager({
        oauthExpirySkewMs: 0,
        oauthMaxRefreshRetries: 1,
        oauthRefreshTimeoutMs: 5000,
        onNodeUpdate: (event) => {
          events.push(event);
        }
      });

      await manager.refreshToken("test", oauthKey);

      // Should have emitted start and complete events
      const startEvent = events.find(e => e.type === "oauth_refresh_start");
      const completeEvent = events.find(e => e.type === "oauth_refresh_complete");
      
      assert(startEvent, "Should emit refresh start event");
      assert(completeEvent, "Should emit refresh complete event");
      assert.strictEqual(completeEvent.data.status, "success");
      
      // Verify no token data is exposed
      assert(!startEvent.data.accessToken);
      assert(!completeEvent.data.accessToken);
    });
  });
});

// Run tests if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  const runTests = async () => {
    console.log("[INFO] Running OAuth utility tests...");
    
    try {
      // Test isOAuthKey
      const validKey = {
        accessToken: "test-token",
        onRefresh: async () => ({ accessToken: "new-token" })
      };
      assert.strictEqual(isOAuthKey(validKey), true, "Should identify valid OAuth key");
      assert.strictEqual(isOAuthKey("string"), false, "Should reject string");
      
      // Test parseExpiresAt
      const epoch = 1640995200000;
      assert.strictEqual(parseExpiresAt(epoch), epoch, "Should parse epoch");
      assert.strictEqual(parseExpiresAt(null), null, "Should return null for null");
      
      // Test isTokenExpired
      const expired = {
        accessToken: "token",
        expiresAt: Date.now() - 10000,
        onRefresh: async () => ({ accessToken: "new" })
      };
      assert.strictEqual(isTokenExpired(expired, 0), true, "Should detect expired token");
      
      // Test OAuthRefreshManager
      const manager = new OAuthRefreshManager({ oauthMaxRefreshRetries: 1, oauthRefreshTimeoutMs: 5000 });
      
      const testKey = {
        accessToken: "old",
        expiresAt: Date.now() - 10000,
        onRefresh: async () => ({
          accessToken: "new",
          expiresAt: Date.now() + 3600000
        })
      };
      
      const refreshed = await manager.refreshToken("test", testKey);
      assert.strictEqual(refreshed.accessToken, "new", "Should refresh token");
      
      console.log("[PASS] All OAuth utility tests passed!");
    } catch (error) {
      console.error("[FAIL] OAuth utility tests failed:", error);
      process.exit(1);
    }
  };
  
  runTests();
}






