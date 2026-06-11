/**
 * Streaming chat proxy: browser → CloudFront → this Lambda → AgentCore Runtime.
 *
 * Receives {session_id, message}, invokes the agent runtime and pipes its SSE
 * byte stream straight back to the client (Lambda RESPONSE_STREAM mode, so
 * tokens reach the browser as the model produces them).
 */

import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from '@aws-sdk/client-bedrock-agentcore';

const client = new BedrockAgentCoreClient({ region: process.env.AGENT_REGION });

const MAX_MESSAGE_CHARS = 2000;
// AgentCore requires runtimeSessionId of at least 33 chars; browser UUIDs (36) fit.
const SESSION_ID_RE = /^[a-zA-Z0-9-]{33,128}$/;

export const handler = awslambda.streamifyResponse(
  async (event, rawStream) => {
    const responseStream = awslambda.HttpResponseStream.from(rawStream, {
      statusCode: 200,
      headers: {
        'content-type': 'text/event-stream',
        'cache-control': 'no-cache',
      },
    });
    const sse = (obj) => responseStream.write(`data: ${JSON.stringify(obj)}\n\n`);

    try {
      const { session_id, message } = JSON.parse(event.body ?? '{}');

      if (!SESSION_ID_RE.test(session_id ?? '') || typeof message !== 'string') {
        sse({ error: 'invalid request' });
        return;
      }

      const prompt = message.trim().slice(0, MAX_MESSAGE_CHARS);
      if (!prompt) {
        sse({ error: 'empty message' });
        return;
      }

      const response = await client.send(
        new InvokeAgentRuntimeCommand({
          agentRuntimeArn: process.env.AGENT_RUNTIME_ARN,
          runtimeSessionId: session_id,
          payload: JSON.stringify({ prompt }),
        }),
      );

      // The runtime already speaks SSE — pipe its bytes through untouched.
      for await (const chunk of response.response) {
        responseStream.write(chunk);
      }
    } catch (err) {
      console.error('chat proxy error:', err);
      sse({ error: 'The assistant is unavailable right now. Please try again.' });
    } finally {
      responseStream.write('data: [DONE]\n\n');
      responseStream.end();
    }
  },
);
