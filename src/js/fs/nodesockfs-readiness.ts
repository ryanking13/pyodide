import {
  createResolvable,
  type ResolvablePromise,
} from "../common/resolveable";

export interface ReadinessSocket {
  // Keep write failures separate from read errors so they don't poison subsequent reads.
  readError: number | null;
  writeError: number | null;
  /** ReadableStream reader for receiving data */
  reader: ReadableStreamDefaultReader<Uint8Array> | null;
  /** WritableStream writer for sending data */
  writer: WritableStreamDefaultWriter<Uint8Array> | null;
  /** Buffer for received data. */
  recvBuffer: Uint8Array[];
  recvBufferBytes: number;
  /** The stream has reached FIN. */
  eof: boolean;
  /** Promise that resolves when data is available. */
  dataAvailable: ResolvablePromise | null;
  readWaiters: Set<ReadinessWaiter>;
  writeWaiters: Set<ReadinessWaiter>;
  pollWaiters: Set<ReadinessWaiter>;
  writerReadyMonitor: WritableStreamDefaultWriter<Uint8Array> | null;
  writerClosedMonitor: WritableStreamDefaultWriter<Uint8Array> | null;
  /** A read() call is in flight on the current ReadableStream reader. */
  readPending: boolean;
  /** Resolves when the current read() call settles. */
  readSettled: Promise<void> | null;
  connected: boolean;
  closed: boolean;
}

type ReadinessWaiter = {
  settle: (ready: boolean) => void;
};

export type ReadinessWatcher = {
  promise: Promise<boolean>;
  cancel: () => void;
  isCurrent: () => boolean;
};

type ReadinessSubscription = {
  promise: Promise<boolean>;
  cancel: () => void;
  settle: (ready: boolean) => void;
  waiter: ReadinessWaiter;
};

export type PollRequest = {
  sock: ReadinessSocket;
  events: number;
};

/**
 * Start a single receive from the underlying ReadableStream.
 * Reads are started by recv()/poll() demand.
 */
export function startRead(sock: ReadinessSocket): void {
  const reader = sock.reader;
  // Not gated on sock.closed: a peer close leaves the reader intact with data
  // and a FIN still to drain, so reads continue until the stream reports done
  // (eof). A local close nulls sock.reader, which the `!reader` guard stops.
  if (sock.readPending || sock.eof || !reader) {
    return;
  }
  sock.readPending = true;

  const readSettled = (async () => {
    try {
      let result: ReadableStreamReadResult<Uint8Array>;
      try {
        result = await reader.read();
      } catch {
        // A reader swap (e.g. startTls) is expected; other errors are not EOF.
        if (sock.reader === reader) {
          sock.readError = cDefs.ECONNRESET;
          notifyDataAvailable(sock);
          notifyReaderReadiness(sock);
          notifyWriterReadiness(sock);
        }
        return;
      }

      // A reader swap can only happen across the await above.
      if (sock.reader !== reader) return;
      if (result.done) {
        sock.eof = true;
        notifyDataAvailable(sock);
        notifyReaderReadiness(sock);
        return;
      }

      sock.recvBuffer.push(result.value);
      sock.recvBufferBytes += result.value.length;
      notifyDataAvailable(sock);
      notifyReaderReadiness(sock);
    } finally {
      sock.readPending = false;
    }
  })();
  sock.readSettled = readSettled;
  // Clean up the readSettled promise when it completes
  readSettled.finally(() => {
    if (sock.readSettled === readSettled) {
      sock.readSettled = null;
    }
  });
}

export function notifyDataAvailable(sock: ReadinessSocket): void {
  if (sock.dataAvailable) {
    sock.dataAvailable.resolve();
    sock.dataAvailable = null;
  }
}

function notifyReadiness(waiters: Set<ReadinessWaiter>): void {
  for (const waiter of waiters) {
    waiter.settle(true);
  }
  waiters.clear();
}

export function notifyReaderReadiness(sock: ReadinessSocket): void {
  notifyReadiness(sock.readWaiters);
  notifyPollReadiness(sock);
}

/**
 * Block until data is available to read or the socket is closed.
 */
export function waitForData(sock: ReadinessSocket): Promise<void> {
  if (sock.recvBufferBytes > 0 || sock.eof) {
    return Promise.resolve();
  }
  if (!sock.reader) {
    return Promise.resolve();
  }
  sock.dataAvailable ??= createResolvable();
  startRead(sock);
  return sock.dataAvailable;
}

/**
 * Observe one readiness transition without consuming socket data.
 */
function createReadinessSubscription(
  waiters: Set<ReadinessWaiter>,
): ReadinessSubscription {
  let settled = false;
  let resolve = (_ready: boolean): void => {};
  const promise = new Promise<boolean>((resolvePromise) => {
    resolve = resolvePromise;
  });
  const settle = (ready: boolean): void => {
    if (!settled) {
      settled = true;
      waiters.delete(waiter);
      resolve(ready);
    }
  };
  const waiter: ReadinessWaiter = { settle };
  return { promise, cancel: () => settle(false), settle, waiter };
}

export function poll(sock: ReadinessSocket): number {
  let mask = 0;

  // Readable: buffered data is ready, or EOF can be observed.
  if (sock.recvBufferBytes > 0 || sock.eof) {
    mask |= cDefs.POLLRDNORM | cDefs.POLLIN;
  }

  // Writable: connected writer with remaining stream capacity.
  if (
    sock.connected &&
    sock.writer &&
    sock.writer.desiredSize !== null &&
    sock.writer.desiredSize > 0
  ) {
    mask |= cDefs.POLLOUT;
  }

  // Hangup: the underlying transport has closed
  if (sock.closed) {
    mask |= cDefs.POLLHUP;
  }

  if (sock.readError !== null || sock.writeError !== null) {
    mask |= cDefs.POLLERR;
  }

  return mask;
}

function readReady(sock: ReadinessSocket): boolean {
  const readableEvents = cDefs.POLLIN | cDefs.POLLRDNORM | cDefs.POLLHUP;
  return sock.readError !== null || !!(poll(sock) & readableEvents);
}

function writeReady(sock: ReadinessSocket): boolean {
  const writableEvents = cDefs.POLLOUT | cDefs.POLLHUP;
  return (
    sock.readError !== null ||
    sock.writeError !== null ||
    !!(poll(sock) & writableEvents)
  );
}

function notifyPollReadiness(sock: ReadinessSocket): void {
  if (poll(sock) & (cDefs.POLLERR | cDefs.POLLHUP)) {
    notifyReadiness(sock.pollWaiters);
  }
}

function subscribePollReadiness(sock: ReadinessSocket): ReadinessSubscription {
  const subscription = createReadinessSubscription(sock.pollWaiters);
  if (poll(sock) & (cDefs.POLLERR | cDefs.POLLHUP)) {
    subscription.settle(true);
  } else {
    sock.pollWaiters.add(subscription.waiter);
  }
  return subscription;
}

export function notifyWriterReadiness(sock: ReadinessSocket): void {
  notifyPollReadiness(sock);
  if (writeReady(sock)) {
    notifyReadiness(sock.writeWaiters);
  } else if (sock.writeWaiters.size) {
    monitorWriterReady(sock);
  }
}

function monitorWriterReady(sock: ReadinessSocket): void {
  const writer = sock.writer;
  if (!writer || sock.writerReadyMonitor === writer) {
    return;
  }
  sock.writerReadyMonitor = writer;
  const monitorSettled = (): void => {
    if (sock.writerReadyMonitor !== writer || sock.writer !== writer) {
      return;
    }
    sock.writerReadyMonitor = null;
    notifyWriterReadiness(sock);
  };
  void writer.ready.then(monitorSettled, monitorSettled);
}

export function monitorWriterClosed(sock: ReadinessSocket): void {
  const writer = sock.writer;
  if (!writer || sock.writerClosedMonitor === writer) {
    return;
  }
  sock.writerClosedMonitor = writer;
  const monitorClosed = (): void => {
    if (sock.writerClosedMonitor !== writer || sock.writer !== writer) {
      return;
    }
    sock.closed = true;
    notifyReaderReadiness(sock);
    notifyWriterReadiness(sock);
  };
  void writer.closed.then(monitorClosed, monitorClosed);
}

function subscribeReadiness(
  sock: ReadinessSocket,
  readable: boolean,
): ReadinessSubscription {
  const waiters = readable ? sock.readWaiters : sock.writeWaiters;
  const subscription = createReadinessSubscription(waiters);
  const ready = readable ? readReady(sock) : writeReady(sock);
  if (ready) {
    subscription.settle(true);
  } else {
    waiters.add(subscription.waiter);
    if (readable && sock.connected) {
      startRead(sock);
    } else if (!readable) {
      monitorWriterReady(sock);
      monitorWriterClosed(sock);
    }
  }
  return subscription;
}

export function watchReadiness(
  sock: ReadinessSocket,
  readable: boolean,
  isCurrent: () => boolean,
): ReadinessWatcher {
  const subscription = subscribeReadiness(sock, readable);
  return {
    promise: subscription.promise,
    cancel: subscription.cancel,
    isCurrent,
  };
}

export async function pollAsync(
  sock: ReadinessSocket,
  events: number,
  timeout: number,
): Promise<number> {
  return (await pollManyAsync([{ sock, events }], timeout))[0];
}

export async function pollManyAsync(
  requests: readonly PollRequest[],
  timeout: number,
): Promise<number[]> {
  // Get the events that are currently ready
  // https://github.com/emscripten-core/emscripten/blob/61533b1fbd7fefc1792220aa0499db1724471e74/src/lib/libsyscall.js#L599
  const getRequestedEvents = (request: PollRequest): number =>
    poll(request.sock) & (request.events | cDefs.POLLERR | cDefs.POLLHUP);
  const getRequestedMasks = (): number[] => requests.map(getRequestedEvents);

  const ready = getRequestedMasks();
  // timeout == 0: No wait, return immediately
  if (ready.some(Boolean) || timeout === 0) return ready;

  const waits: ReadinessSubscription[] = [];
  for (const request of requests) {
    if (request.events & (cDefs.POLLIN | cDefs.POLLRDNORM)) {
      waits.push(subscribeReadiness(request.sock, true));
    }
    if (request.events & cDefs.POLLOUT) {
      waits.push(subscribeReadiness(request.sock, false));
    }
    waits.push(subscribePollReadiness(request.sock));
  }

  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  try {
    const readiness = Promise.race(waits.map((wait) => wait.promise));
    if (timeout < 0) {
      await readiness;
    } else {
      await Promise.race([
        readiness,
        new Promise<void>((resolve) => {
          timeoutId = setTimeout(resolve, timeout);
        }),
      ]);
    }
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
    for (const wait of waits) {
      wait.cancel();
    }
  }
  return getRequestedMasks();
}
