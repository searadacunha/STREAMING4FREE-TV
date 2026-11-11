package com.local.streaming4free

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ParseM3uTest {
    @Test
    fun keepsPlayableEntriesWithTheirAttributes() {
        val list = parseM3u(sequenceOf(
            "﻿#EXTM3U url-tvg=\"https://example.com/epg.xml\"",
            "#EXTINF:-1 tvg-id=\"RTP1.pt\" tvg-logo=\"https://example.com/rtp1.png\" group-title=\"TV\",RTP 1",
            "#EXTVLCOPT:http-referrer=https://www.rtp.pt/",
            "https://example.com/rtp1.m3u8",
            "",
            "#EXTINF:-1 group-title=\"News;Public\",Name, with a comma",
            "  http://example.com/news.m3u8  ",
            "#EXTINF:-1,Clear-key DRM channel",
            "#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey",
            "#KODIPROP:inputstream.adaptive.license_key=0123:4567",
            "https://example.com/drm.mpd",
            "#EXTINF:-1,RTMP channel",
            "rtmp://example.com/live",
            "#EXTINF:-1 tvg-name=\"From tvg-name\",",
            "https://example.com/named.m3u8",
            "https://example.com/orphan-url-without-extinf.m3u8",
        ), "Test")

        assertEquals(listOf("RTP 1", "Name, with a comma", "From tvg-name"), list.map { it.title })
        val rtp = list[0]
        assertEquals("https://example.com/rtp1.m3u8", rtp.url)
        assertEquals("https://example.com/rtp1.png", rtp.logo)
        assertEquals("TV", rtp.group)
        assertEquals("RTP1.pt", rtp.id)
        assertEquals("Test", rtp.source)
        assertEquals("http://example.com/news.m3u8", list[1].url)
        assertEquals("News;Public", list[1].group)
    }

    @Test
    fun recognisesYouTubePages() {
        assertTrue(Channel("a", "https://www.youtube.com/c/franceinfo/live").isYouTube)
        assertTrue(Channel("a", "https://youtu.be/abc").isYouTube)
        assertFalse(Channel("a", "https://example.com/youtube.com/x.m3u8").isYouTube)
    }
}
