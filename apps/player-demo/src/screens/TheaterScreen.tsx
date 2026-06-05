import { Ionicons } from "@expo/vector-icons";
import { useCallback, useEffect, useRef, useState } from "react";
import { FlatList, Image, NativeScrollEvent, NativeSyntheticEvent, Pressable, StyleSheet, Text, View } from "react-native";
import { PlayerBottomTabs } from "../components/PlayerBottomTabs";
import { shouldRestoreScrollOffset, type SeriesGroup } from "../domain/playerFeed";
import { getSeriesCoverSource } from "../domain/seriesCovers";
import { colors, radii, spacing } from "../theme";

export function TheaterScreen({
  series,
  resumeVideoIds,
  initialScrollOffset,
  onSelectSeries,
  onScrollOffsetChange,
  onOpenHome
}: {
  series: SeriesGroup[];
  resumeVideoIds: Record<string, string>;
  initialScrollOffset: number;
  onSelectSeries: (series: SeriesGroup) => void;
  onScrollOffsetChange: (offset: number) => void;
  onOpenHome: () => void;
}) {
  const listRef = useRef<FlatList<SeriesGroup>>(null);
  const [didRestoreOffset, setDidRestoreOffset] = useState(false);

  const handleScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    onScrollOffsetChange(event.nativeEvent.contentOffset.y);
  };

  const restoreScrollOffset = useCallback(() => {
    if (didRestoreOffset || !shouldRestoreScrollOffset({ offset: initialScrollOffset, itemCount: series.length })) {
      return;
    }
    requestAnimationFrame(() => {
      listRef.current?.scrollToOffset({ offset: initialScrollOffset, animated: false });
      setDidRestoreOffset(true);
    });
  }, [didRestoreOffset, initialScrollOffset, series.length]);

  useEffect(() => {
    setDidRestoreOffset(false);
  }, [initialScrollOffset]);

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={22} color="#8F8F8F" />
          <Text numberOfLines={1} style={styles.searchText}>
            搜索短剧名、角色或高光剧情
          </Text>
        </View>
      </View>
      <FlatList
        ref={listRef}
        contentContainerStyle={styles.listContent}
        columnWrapperStyle={styles.row}
        data={series}
        keyExtractor={(item) => item.seriesKey}
        numColumns={2}
        showsVerticalScrollIndicator={false}
        scrollEventThrottle={250}
        onScroll={handleScroll}
        onLayout={restoreScrollOffset}
        onContentSizeChange={restoreScrollOffset}
        renderItem={({ item }) => {
          const coverSource = getSeriesCoverSource(item.coverVideo.seriesId) ?? { uri: item.coverVideo.streamUrl };
          return (
            <Pressable accessibilityRole="button" style={styles.card} onPress={() => onSelectSeries(item)}>
              <View style={styles.cover}>
                <Image source={coverSource} style={styles.coverImage} />
              </View>
              <Text numberOfLines={2} style={styles.title}>
                {item.title}
              </Text>
            </Pressable>
          );
        }}
      />
      <PlayerBottomTabs
        activeTab="剧场"
        presentation="docked"
        onPressHome={onOpenHome}
        onPressTheater={() => undefined}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#FAFAFA"
  },
  header: {
    paddingTop: 54,
    paddingHorizontal: spacing.lg,
    paddingBottom: 10
  },
  searchBox: {
    height: 44,
    paddingHorizontal: spacing.md,
    borderRadius: radii.small,
    backgroundColor: colors.text,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.06,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 8 }
  },
  searchText: {
    flex: 1,
    color: "#9A9A9A",
    fontSize: 16,
    fontWeight: "700"
  },
  listContent: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md
  },
  row: {
    gap: spacing.md
  },
  card: {
    flex: 1,
    minWidth: 0,
    marginBottom: spacing.md
  },
  cover: {
    aspectRatio: 0.72,
    overflow: "hidden",
    borderRadius: 6,
    backgroundColor: "#D9D9D9"
  },
  coverImage: {
    width: "100%",
    height: "100%"
  },
  title: {
    minHeight: 48,
    marginTop: spacing.sm,
    color: "#151515",
    fontSize: 17,
    fontWeight: "800",
    lineHeight: 23
  }
});
