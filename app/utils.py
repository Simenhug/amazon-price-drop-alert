import functools
import time


class RetryOnException:
    def __init__(self, exception=Exception, retries=3, delay=1):
        """
        :param exception: The exception to catch and retry
        :param retries: Number of times to retry before failing
        :param delay: Seconds to wait between retries
        """
        self.exception = exception
        self.retries = retries
        self.delay = delay

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < self.retries:
                try:
                    return func(*args, **kwargs)
                except self.exception as e:
                    attempt += 1
                    print(f"Attempt {attempt} failed: {e}")
                    if attempt < self.retries:
                        time.sleep(self.delay)  # Optional: wait before retrying
                    else:
                        print("Max retries reached. Raising exception.")
                        raise

        return wrapper
