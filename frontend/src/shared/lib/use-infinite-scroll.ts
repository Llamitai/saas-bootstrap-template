import { useEffect, useRef } from "react";

export function useInfiniteScroll(
  fetchNextPage: () => void,
  hasNextPage: boolean | undefined,
  isFetchingNextPage: boolean,
  threshold = 150
) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const canLoadMoreRef = useRef(false);
  const doLoadMoreRef = useRef<() => void>(() => {});

  useEffect(() => {
    canLoadMoreRef.current = !!hasNextPage && !isFetchingNextPage;
    doLoadMoreRef.current = fetchNextPage;
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    const handleScroll = () => {
      const { scrollTop, clientHeight, scrollHeight } = element;
      if (
        scrollHeight - scrollTop - clientHeight < threshold &&
        canLoadMoreRef.current
      ) {
        doLoadMoreRef.current();
      }
    };
    element.addEventListener("scroll", handleScroll);
    return () => element.removeEventListener("scroll", handleScroll);
  }, [threshold]);

  return scrollRef;
}
