"""
Fiery PPD option definitions for the RoutingPreset form.

Each section is a tuple of (section_title, options_list).
Each option is a tuple of (ppd_key, display_label, choices_list).
Each choice is a tuple of (ppd_value, display_label).

An empty string value "" means "don't send this option" (use printer default).

These definitions are sourced directly from the fiery_hold CUPS PPD
as reported by: lpoptions -p fiery_hold -l
"""

# Reused tray list (InputSlot / EFBookCoverTray / EFPadBackCoverTray)
_TRAY_CHOICES = [
    ("", "— printer default —"),
    ("AutoSelect", "Auto Select"),
    ("Tray1", "Tray 1"),
    ("Tray2", "Tray 2"),
    ("HighCapacityInputBin1", "High Capacity Input Bin 1"),
    ("PaperFeedUnit1", "Paper Feed Unit 1"),
    ("PaperFeedUnit2", "Paper Feed Unit 2"),
    ("Tray3", "Tray 3"),
    ("Tray4", "Tray 4"),
    ("Tray5", "Tray 5"),
    ("ManualFeed", "Manual Feed"),
    ("PostFuserTray", "Post Fuser Tray"),
    ("PostFuserTray2", "Post Fuser Tray 2"),
    ("PBTray", "PB Tray"),
    ("Tray6", "Tray 6"),
    ("Tray7", "Tray 7"),
    ("Tray8", "Tray 8"),
    ("Tray9", "Tray 9"),
    ("Tray10", "Tray 10"),
    ("Tray11", "Tray 11"),
]

# EFPadBackCoverTray excludes AutoSelect
_PAD_COVER_TRAY_CHOICES = [c for c in _TRAY_CHOICES if c[0] != "AutoSelect"]

FIERY_OPTION_SECTIONS = [
    # ── Media ────────────────────────────────────────────────────────────────
    (
        "Media",
        [
            (
                "EFPrintSize",
                "Paper Size",
                [
                    ("", "— printer default —"),
                    ("SameAsPageSize", "Same as Document"),
                    ("Letter", "Letter (8.5×11)"),
                    ("LetterR", "Letter Rotated"),
                    ("A4", "A4"),
                    ("A4R", "A4 Rotated"),
                    ("A3", "A3"),
                    ("A5", "A5"),
                    ("A5R", "A5 Rotated"),
                    ("A6R", "A6 Rotated"),
                    ("Legal", "Legal (8.5×14)"),
                    ("Tabloid", "Tabloid (11×17)"),
                    ("TabloidExtra", "Tabloid Extra (12×18)"),
                    ("StatementR", "Statement Rotated"),
                    ("B4", "B4"),
                    ("B5", "B5"),
                    ("B5R", "B5 Rotated"),
                    ("B6R", "B6 Rotated"),
                    ("K8", "K8"),
                    ("SRA3", "SRA3"),
                    ("SRA4", "SRA4"),
                    ("SRA4R", "SRA4 Rotated"),
                    ("M16KSpecial", "M16K Special"),
                    ("M16KSpecialRotated", "M16K Special Rotated"),
                    ("13x19", "13×19"),
                    ("8x13", "8×13"),
                    ("9x11", "9×11"),
                    ("A4Tab", "A4 Tab"),
                    ("A4TabThreeEightsInch", "A4 Tab 3/8\""),
                    ("ISOB4", "ISO B4"),
                    ("ISOB5", "ISO B5"),
                    ("ISOB5R", "ISO B5 Rotated"),
                    ("ISOB6", "ISO B6"),
                    ("9.06x11", "9.06×11"),
                    ("CustomPrintSize", "Custom"),
                ],
            ),
            (
                "EFMediaType",
                "Paper Type",
                [
                    ("", "— printer default —"),
                    ("EFMediaTypeDEF", "Fiery Default"),
                    ("Any", "Any"),
                    ("Plain", "Plain"),
                    ("Color", "Color"),
                    ("HighQuality", "High Quality"),
                    ("CoatedGlossOffset", "Coated Gloss Offset"),
                    ("CoatedMatteOffset", "Coated Matte Offset"),
                    ("Envelope", "Envelope"),
                    ("Embossed2", "Embossed"),
                ],
            ),
            (
                "EFMediaColor",
                "Paper Color",
                [
                    ("", "— printer default —"),
                    ("EFMediaColorDEF", "Fiery Default"),
                    ("Any", "Any"),
                    ("White", "White"),
                    ("Cream", "Cream"),
                    ("Blue", "Blue"),
                    ("Goldenrod", "Goldenrod"),
                    ("Gray", "Gray"),
                    ("Green", "Green"),
                    ("Ivory", "Ivory"),
                    ("Orange", "Orange"),
                    ("Pink", "Pink"),
                    ("Red", "Red"),
                    ("Yellow", "Yellow"),
                    ("Custom1", "Custom 1"),
                ],
            ),
            (
                "EFMediaHoleType",
                "Punched Paper",
                [
                    ("", "— printer default —"),
                    ("EFMediaHoleTypeDEF", "Fiery Default"),
                    ("Any", "Any"),
                    ("None", "None"),
                    ("S-generic", "S-generic"),
                ],
            ),
            (
                "EFMediaWeight",
                "Paper Weight",
                [
                    ("", "— printer default —"),
                    ("EFMediaWeightDEF", "Fiery Default"),
                    ("Any", "Any"),
                    ("62_74", "62–74 gsm"),
                    ("75_80", "75–80 gsm"),
                    ("81_91", "81–91 gsm"),
                    ("92_105", "92–105 gsm"),
                    ("106_135", "106–135 gsm"),
                    ("136_176", "136–176 gsm"),
                    ("177_216", "177–216 gsm"),
                    ("217_256", "217–256 gsm"),
                    ("257_300", "257–300 gsm"),
                    ("301_350", "301–350 gsm"),
                    ("351_360", "351–360 gsm"),
                ],
            ),
            (
                "InputSlot",
                "Input Tray",
                _TRAY_CHOICES[:],
            ),
        ],
    ),

    # ── Print Queue Action ────────────────────────────────────────────────────
    (
        "Print Queue Action",
        [
            (
                "EFRaster",
                "Queue Action",
                [
                    ("", "— printer default —"),
                    ("False", "Normal (Print)"),
                    ("True", "Process and Hold"),
                    ("RipNHold", "RIP and Hold"),
                    ("Hold", "Hold"),
                    ("PrintNDelete", "Print and Delete"),
                ],
            ),
            (
                "EFDisplayJobTracking",
                "Enable Job Tracking",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFAccountSetting",
                "Account Settings",
                [
                    ("", "— printer default —"),
                    ("AlwaysEnter", "Always Enter"),
                    ("AlwaysUseLast", "Always Use Last"),
                ],
            ),
            (
                "EFAccountShowLast",
                "Show Last Account Info",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
        ],
    ),

    # ── Color ─────────────────────────────────────────────────────────────────
    (
        "Color",
        [
            (
                "EFColorMode",
                "Color Mode",
                [
                    ("", "— printer default —"),
                    ("CMYK", "CMYK (Color)"),
                    ("Grayscale", "Grayscale"),
                ],
            ),
            (
                "EFSimulation",
                "CMYK Source Profile",
                [
                    ("", "— printer default —"),
                    ("EFSimulationDEF", "Fiery Default"),
                    ("SIMNONE", "None"),
                    ("MATCHCOPY", "Match Copy"),
                    ("GRACOL2013", "GRACoL 2013"),
                    ("FOGRA51", "FOGRA51"),
                    ("FOGRA52", "FOGRA52"),
                    ("SWOP2013CRPC5", "SWOP 2013 CRPC5"),
                    ("JAPANCOLOR2011", "Japan Color 2011"),
                    ("DIC", "DIC"),
                    ("TOYOCOATED", "Toyo Coated"),
                ],
            ),
            (
                "EFOutProfile",
                "Output Profile",
                [
                    ("", "— printer default —"),
                    ("EFOutProfileDEF", "Fiery Default"),
                    ("DEFAULT_MEDIA", "Use Media Default"),
                    ("OUT1", "Output 1"),
                    ("OUT2", "Output 2"),
                    ("OUT3", "Output 3"),
                    ("OUT4", "Output 4"),
                    ("OUT5", "Output 5"),
                    ("OUT6", "Output 6"),
                    ("OUT7", "Output 7"),
                    ("OUT8", "Output 8"),
                    ("OUT9", "Output 9"),
                    ("OUT10", "Output 10"),
                ],
            ),
            (
                "EFPureBlack",
                "Black Text & Graphics",
                [
                    ("", "— printer default —"),
                    ("EFPureBlackDEF", "Fiery Default"),
                    ("BLACKPUREON", "Pure Black On"),
                    ("BLACKRICHON", "Rich Black On"),
                    ("BLACKNORMAL", "Normal"),
                ],
            ),
            (
                "EFBlkOvpCtrl",
                "Black Overprint",
                [
                    ("", "— printer default —"),
                    ("EFBlkOvpCtrlDEF", "Fiery Default"),
                    ("TEXTGRAPHICS", "Text & Graphics"),
                    ("TEXTONLY", "Text Only"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFHPBlack",
                "Black Detection",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFSpotColors",
                "Spot Color Matching",
                [
                    ("", "— printer default —"),
                    ("EFSpotColorsDEF", "Fiery Default"),
                    ("ON", "On"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFSpotPriority",
                "Spot Color Group",
                [
                    ("", "— printer default —"),
                    ("Default", "Default"),
                ],
            ),
            (
                "EFSpotOvpStrategy",
                "Spot Color Overprint",
                [
                    ("", "— printer default —"),
                    ("CMYK", "CMYK"),
                    ("RGB", "RGB"),
                    ("Lab", "Lab"),
                ],
            ),
            (
                "EFCurveAdjSpotBypass",
                "Preserve Spot Colors",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFTrapping",
                "Auto Trapping",
                [
                    ("", "— printer default —"),
                    ("EFTrappingDEF", "Fiery Default"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFTrappingCutback",
                "Cutback Trapping",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("BlackSep", "Black Separation"),
                    ("AllSeps", "All Separations"),
                ],
            ),
            (
                "EFCompOverprint",
                "Composite Overprint",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFSubstColors",
                "Substitute Colors",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFMltClrPrntMap",
                "2-Color Print Mapping",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
        ],
    ),

    # ── Layout ────────────────────────────────────────────────────────────────
    (
        "Layout",
        [
            (
                "EFDuplex",
                "Duplex",
                [
                    ("", "— printer default —"),
                    ("False", "Simplex (1-sided)"),
                    ("TopTop", "Duplex Long-Edge"),
                    ("TopBottom", "Duplex Short-Edge"),
                ],
            ),
            (
                "EFDrvOrientation",
                "Orientation",
                [
                    ("", "— printer default —"),
                    ("Portrait", "Portrait"),
                    ("Landscape", "Landscape"),
                ],
            ),
            (
                "EFAutoScaling",
                "Scale to Fit",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                    ("ScaleToPaperSize", "Scale to Paper Size"),
                ],
            ),
            (
                "EFDrvMirror",
                "Mirror Print",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFUserRotate180",
                "Rotate 180°",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFNUpOption",
                "N-Up Layout",
                [
                    ("", "— printer default —"),
                    ("1UP", "1-Up (Normal)"),
                    ("2ULH", "2-Up Landscape (H)"),
                    ("2URV", "2-Up Portrait (V)"),
                    ("2ULV", "2-Up Portrait (V2)"),
                    ("2URH", "2-Up Rotated (H)"),
                    ("4ULH", "4-Up Landscape (H)"),
                    ("4ULV", "4-Up Portrait (V)"),
                    ("4URH", "4-Up Rotated (H)"),
                    ("4URV", "4-Up Rotated (V)"),
                    ("6ULH", "6-Up Landscape (H)"),
                    ("6ULV", "6-Up Portrait (V)"),
                    ("6URH", "6-Up Rotated (H)"),
                    ("6URV", "6-Up Rotated (V)"),
                    ("9ULH", "9-Up Landscape (H)"),
                    ("9ULV", "9-Up Portrait (V)"),
                    ("9URH", "9-Up Rotated (H)"),
                    ("9URV", "9-Up Rotated (V)"),
                    ("16ULH", "16-Up Landscape (H)"),
                    ("16ULV", "16-Up Portrait (V)"),
                    ("16URH", "16-Up Rotated (H)"),
                    ("16URV", "16-Up Rotated (V)"),
                ],
            ),
            (
                "EFNUpBoundingBox",
                "N-Up Border",
                [
                    ("", "— printer default —"),
                    ("False", "No Border"),
                    ("True", "With Border"),
                ],
            ),
            (
                "EFMMInUse",
                "Mixed Media In Use",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFMMInsType",
                "Mixed Media Insertion Type",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("Blank", "Blank"),
                    ("Tab", "Tab"),
                ],
            ),
            (
                "EFMMCover",
                "Cover Page Mode",
                [
                    ("", "— printer default —"),
                    ("PrintBoth", "Print Both"),
                    ("PrintFront", "Print Front"),
                    ("PrintBack", "Print Back"),
                ],
            ),
            (
                "EFMMTabShift",
                "Tab Shift",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFMicroRotationDirection",
                "Micro Rotation Direction",
                [
                    ("", "— printer default —"),
                    ("OFF", "Off"),
                    ("CLOCKWISE", "Clockwise"),
                    ("COUNTER_CLOCKWISE", "Counter Clockwise"),
                ],
            ),
            (
                "EFImageFlag",
                "Image Shift",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFImageOffsetOutput",
                "Apply Offset To",
                [
                    ("", "— printer default —"),
                    ("FrontOnly", "Front Only"),
                    ("FrontAndBack", "Front and Back"),
                ],
            ),
            (
                "EFImageAlign",
                "Align Front & Back Images",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFImageUnitOutput",
                "Image Offset Units",
                [
                    ("", "— printer default —"),
                    ("MM", "Millimeters"),
                    ("Inches", "Inches"),
                ],
            ),
            (
                "EFImageUnit",
                "Image Shift Units",
                [
                    ("", "— printer default —"),
                    ("Inches", "Inches"),
                    ("MM", "Millimeters"),
                    ("Points", "Points"),
                ],
            ),
        ],
    ),

    # ── Output & Delivery ─────────────────────────────────────────────────────
    (
        "Output & Delivery",
        [
            (
                "EFOutputBin",
                "Output Tray",
                [
                    ("", "— printer default —"),
                    ("AutoSelect", "Auto Select"),
                    ("Outbin1", "Outbin 1"),
                    ("Outbin2", "Outbin 2"),
                    ("Outbin3", "Outbin 3"),
                    ("Outbin4", "Outbin 4"),
                    ("Outbin5", "Outbin 5"),
                    ("Outbin6", "Outbin 6"),
                    ("Outbin7", "Outbin 7"),
                    ("Outbin8", "Outbin 8"),
                    ("Outbin9", "Outbin 9"),
                    ("Outbin10", "Outbin 10"),
                    ("Outbin12", "Outbin 12"),
                    ("Outbin13", "Outbin 13"),
                    ("Outbin14", "Outbin 14"),
                    ("Outbin15", "Outbin 15"),
                    ("Stacker", "Stacker"),
                    ("Stapler", "Stapler"),
                    ("ExternalFinisher", "External Finisher"),
                    ("RelayUnit", "Relay Unit"),
                    ("RelayUnit2", "Relay Unit 2"),
                    ("Trimmer", "Trimmer"),
                    ("Trimmer2", "Trimmer 2"),
                ],
            ),
            (
                "EFSort",
                "Sort / Group",
                [
                    ("", "— printer default —"),
                    ("Sort", "Sort (Collated)"),
                    ("Group", "Group (Uncollated)"),
                ],
            ),
            (
                "EFPageDelivery",
                "Page Face",
                [
                    ("", "— printer default —"),
                    ("SameOrderFaceDown", "Same Order Face Down"),
                    ("SameOrderFaceUp", "Same Order Face Up"),
                    ("ReverseOrderFaceDown", "Reverse Order Face Down"),
                    ("ReverseOrderFaceUp", "Reverse Order Face Up"),
                ],
            ),
            (
                "EFOffsetWithinJob",
                "Offset Within Job",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFOffsetBoundary",
                "Offset Boundary",
                [
                    ("", "— printer default —"),
                    ("Sheets", "Sheets"),
                    ("Copies", "Copies"),
                    ("Sets", "Sets"),
                ],
            ),
            (
                "EFChangeOffsetPosition",
                "Offset Jobs",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFJobStacking",
                "Allow Job Stacking",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                    ("This", "This Job"),
                    ("Next", "Next Job"),
                ],
            ),
            (
                "EFPaperDeckOpt",
                "Optional Feeder",
                [
                    ("", "— printer default —"),
                    ("Bypass", "Bypass"),
                    ("BypassLargeCapTray", "Bypass Large Capacity Tray"),
                    ("Option2", "Option 2"),
                    ("Option5", "Option 5"),
                    ("Option6", "Option 6"),
                    ("Option7", "Option 7"),
                    ("Option8", "Option 8"),
                    ("Option9", "Option 9"),
                    ("Option10", "Option 10"),
                    ("Option11", "Option 11"),
                    ("Option12", "Option 12"),
                    ("Option13", "Option 13"),
                ],
            ),
            (
                "EFStacker",
                "Stacker",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("LargeCapacityStacker", "Large Capacity Stacker"),
                    ("Dual", "Dual"),
                    ("True", "On"),
                    ("Option3", "Option 3"),
                    ("Option4", "Option 4"),
                ],
            ),
            (
                "EFEngineWait",
                "Wait",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFExternalFinishing",
                "External Finishing",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
        ],
    ),

    # ── Finishing ────────────────────────────────────────────────────────────
    (
        "Finishing",
        [
            (
                "EFStapler",
                "Staple",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("1UpLeftS", "1 Staple — Left Skewed"),
                    ("1UpRightS", "1 Staple — Right Skewed"),
                    ("2Left", "2 Staples — Left Edge"),
                    ("2Right", "2 Staples — Right Edge"),
                    ("2Up", "2 Staples — Top Edge"),
                    ("Center", "Center"),
                    ("4Center", "4 Center"),
                ],
            ),
            (
                "EFStaplePitch",
                "Staple Pitch",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("Narrow", "Narrow"),
                    ("Middle1", "Middle"),
                    ("Wide", "Wide"),
                ],
            ),
            (
                "EFPunchEdge",
                "Punch Edge",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("Left", "Left"),
                    ("Right", "Right"),
                    ("Top", "Top"),
                ],
            ),
            (
                "EFPunchHoleType",
                "Punch Holes",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("2Even", "2 Holes"),
                    ("3Even", "3 Holes"),
                    ("4Even", "4 Holes"),
                    ("MultiPunch", "Multi-Punch"),
                    ("DoubleMultiPunch", "Double Multi-Punch"),
                ],
            ),
            (
                "EFFold",
                "Fold Style",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("HalfFold", "Half Fold"),
                    ("HalfZFold", "Half Z-Fold"),
                    ("TriFold", "Tri-Fold"),
                    ("Zfold", "Z-Fold"),
                    ("DoubleHalfFold", "Double Half Fold"),
                    ("GateFold", "Gate Fold"),
                    ("CollateHalfFold", "Collate Half Fold"),
                    ("CollateTriFold", "Collate Tri-Fold"),
                    ("SpineHalfFold", "Spine Half Fold"),
                ],
            ),
            (
                "EFFoldOrder",
                "Fold Print Side",
                [
                    ("", "— printer default —"),
                    ("In", "In"),
                    ("Out", "Out"),
                ],
            ),
            (
                "EFCrease",
                "Crease",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("CollateTriFold", "Collate Tri-Fold"),
                    ("Perfect", "Perfect"),
                    ("Saddle", "Saddle"),
                ],
            ),
            (
                "EFCreaseType",
                "Crease Type",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("SpineGutter", "Spine Gutter"),
                    ("Gutter", "Gutter"),
                    ("Spine", "Spine"),
                ],
            ),
            (
                "EFSlit",
                "2-Side Slit",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("All", "All"),
                    ("Cover", "Cover"),
                ],
            ),
            (
                "EFSlitUnit",
                "Slit Units",
                [
                    ("", "— printer default —"),
                    ("MM", "Millimeters"),
                    ("Inches", "Inches"),
                ],
            ),
            (
                "EFTrimmer",
                "Fore-edge Trim",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFPBTrimMode",
                "Cover Trim",
                [
                    ("", "— printer default —"),
                    ("1Way", "1 Way"),
                    ("Off", "Off"),
                ],
            ),
            (
                "EFPressAdjustment",
                "Spine Corner Forming Strength",
                [
                    ("", "— printer default —"),
                    ("-2", "-2"),
                    ("-1", "-1"),
                    ("0", "0 (Default)"),
                    ("1", "+1"),
                    ("2", "+2"),
                ],
            ),
            (
                "EFPadCover",
                "Add Pad Back Cover",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFPadPrinting",
                "Enable Pad Printing",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFPadBackCoverTray",
                "Pad Back Cover Source",
                _PAD_COVER_TRAY_CHOICES[:],
            ),
            (
                "EFSubsetFinishingInUse",
                "Subset Finishing",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
        ],
    ),

    # ── Booklet ───────────────────────────────────────────────────────────────
    (
        "Booklet",
        [
            (
                "EFRIPBooklet",
                "Booklet Type",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("TwoUp", "2-Up Saddle"),
                    ("TwoUpRight", "2-Up Saddle (Right Binding)"),
                    ("TwoUpTop", "2-Up Top"),
                    ("Perfect", "Perfect Binding"),
                    ("PerfectRight", "Perfect Binding (Right)"),
                    ("PerfectTop", "Perfect Top"),
                    ("NestSaddleL", "Nested Saddle Left"),
                    ("NestSaddleR", "Nested Saddle Right"),
                    ("NestSaddleT", "Nested Saddle Top"),
                    ("Speed", "Speed"),
                    ("Double", "Double"),
                    ("WrapCoverBookL", "Wrap Cover Book Left"),
                    ("WrapCoverBookR", "Wrap Cover Book Right"),
                    ("WrapCoverBookT", "Wrap Cover Book Top"),
                ],
            ),
            (
                "EFBookCoverEnabled",
                "Cover Enabled",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFBookFrCover",
                "Front Cover",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("Side1", "Side 1"),
                    ("Side2", "Side 2"),
                    ("Both", "Both Sides"),
                    ("Blank", "Blank"),
                ],
            ),
            (
                "EFBookBkCover",
                "Back Cover",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("Side1", "Side 1"),
                    ("Side2", "Side 2"),
                    ("Both", "Both Sides"),
                    ("Blank", "Blank"),
                ],
            ),
            (
                "EFBookCoverTray",
                "Booklet Cover Source",
                _TRAY_CHOICES[:],
            ),
            (
                "EFBookCoverInType",
                "Cover Input Type",
                [
                    ("", "— printer default —"),
                    ("TwoPageSpread", "Two Page Spread"),
                    ("MultiPageNoSpine", "Multi Page No Spine"),
                    ("PrePrinted", "Pre-Printed"),
                    ("SinglePageSpread", "Single Page Spread"),
                ],
            ),
            (
                "EFBookletCreep",
                "Creep Adjustment",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("Plain", "Plain"),
                    ("Thick", "Thick"),
                ],
            ),
            (
                "EFBookletReduce",
                "Shrink to Fit",
                [
                    ("", "— printer default —"),
                    ("True", "Yes"),
                    ("False", "No"),
                ],
            ),
            (
                "EFBookNumSheetPerSubset",
                "Sheets per Subset (Saddle)",
                [("", "— printer default —")]
                + [(str(n), str(n)) for n in range(2, 21)],
            ),
            (
                "EFBookCentering",
                "Align Pages",
                [
                    ("", "— printer default —"),
                    ("Bottom", "Bottom"),
                    ("Middle", "Middle"),
                ],
            ),
            (
                "EFBookSpineContentType",
                "Spine Content",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("DocPage", "Document Page"),
                ],
            ),
            (
                "EFBookScaling",
                "Booklet Scaling",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("ShrinkToBody", "Shrink to Body"),
                ],
            ),
            (
                "EFEngageTU510",
                "Use Inline Trimmer",
                [
                    ("", "— printer default —"),
                    ("True", "Yes"),
                    ("False", "No"),
                ],
            ),
        ],
    ),

    # ── Slip Sheet ────────────────────────────────────────────────────────────
    (
        "Slip Sheet",
        [
            (
                "EFSlipsheet",
                "Slip Sheet",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFSlipSheetBoundary",
                "Slip Sheet Between",
                [
                    ("", "— printer default —"),
                    ("Sheets", "Sheets"),
                    ("Copies", "Copies"),
                    ("Sets", "Sets"),
                ],
            ),
            (
                "EFSlipSheetPaperCatalog",
                "Slip Sheet Media",
                [
                    ("", "— printer default —"),
                    ("SameAsJob", "Same As Job"),
                    ("_Custom", "Custom"),
                ],
            ),
        ],
    ),

    # ── Banner & Cover Page ───────────────────────────────────────────────────
    (
        "Banner & Cover Page",
        [
            (
                "EFBannerPage",
                "Banner Page",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFBannerPageCount",
                "Banner Pages Count",
                [
                    ("", "— printer default —"),
                    ("1", "1"),
                    ("2", "2"),
                    ("3", "3"),
                    ("4", "4"),
                    ("5", "5"),
                ],
            ),
            (
                "EFBannerSource",
                "Banner Source",
                [
                    ("", "— printer default —"),
                    ("Templates", "Templates"),
                    ("Document", "Document"),
                ],
            ),
            (
                "EFPrintCover",
                "Banner Page Position",
                [
                    ("", "— printer default —"),
                    ("BeforeJob", "Before Job"),
                    ("AfterJob", "After Job"),
                    ("BeforeAndAfter", "Before and After"),
                ],
            ),
            (
                "EFCoverPagePaperCatalog",
                "Cover Page Media",
                [
                    ("", "— printer default —"),
                    ("SameAsJob", "Same As Job"),
                    ("_Custom", "Custom"),
                ],
            ),
        ],
    ),

    # ── Print Quality ─────────────────────────────────────────────────────────
    (
        "Print Quality",
        [
            (
                "EFResolution",
                "Resolution",
                [
                    ("", "— printer default —"),
                    ("1200x1200dpi", "1200×1200 dpi"),
                    ("600x600dpi", "600×600 dpi"),
                ],
            ),
            (
                "EFHTScreen",
                "Halftone Simulation",
                [
                    ("", "— printer default —"),
                    ("Contone", "Contone"),
                    ("AppDef", "Application Defined"),
                    ("Newsprint", "Newsprint"),
                    ("Screen1", "Screen 1"),
                    ("Screen2", "Screen 2"),
                    ("Screen3", "Screen 3"),
                ],
            ),
            (
                "EFIQHTScreen",
                "Image Halftone Screen",
                [
                    ("", "— printer default —"),
                    ("Line1", "Line 1"),
                    ("Line2", "Line 2"),
                    ("Stochastic", "Stochastic"),
                ],
            ),
            (
                "EFIQTxGrfxHTScreen",
                "Text/Graphics Halftone Screen",
                [
                    ("", "— printer default —"),
                    ("SameAsImage", "Same as Image"),
                    ("Line1", "Line 1"),
                    ("Line2", "Line 2"),
                ],
            ),
            (
                "EFJobExpertRule",
                "JobExpert Rule",
                [
                    ("", "— printer default —"),
                    ("ServerDefault", "Server Default"),
                ],
            ),
            (
                "EFMinStrokeWidth",
                "Minimum Stroke Width",
                [
                    ("", "— printer default —"),
                    ("1", "1"),
                    ("2", "2"),
                ],
            ),
            (
                "EFCompression",
                "Image Quality",
                [
                    ("", "— printer default —"),
                    ("BestQuality", "Best"),
                    ("NormalQuality", "Normal"),
                ],
            ),
            (
                "EFTextGfxQual",
                "Text / Graphics Quality",
                [
                    ("", "— printer default —"),
                    ("EFTextGfxQualDEF", "Fiery Default"),
                    ("Best", "Best"),
                    ("Normal", "Normal"),
                ],
            ),
            (
                "EFIQTonerReduce",
                "Toner Reduction",
                [
                    ("", "— printer default —"),
                    ("Off", "Off"),
                    ("On", "On"),
                    ("Draft", "Draft"),
                ],
            ),
            (
                "EFMaxPrintDensity",
                "Max Print Density",
                [
                    ("", "— printer default —"),
                    ("False", "Normal"),
                    ("True", "Maximum"),
                ],
            ),
            (
                "EFBrightness",
                "Brightness",
                [
                    ("", "— printer default —"),
                    ("0.24", "+24% (Lightest)"),
                    ("0.16", "+16% (Lighter)"),
                    ("0.08", "+8% (Light)"),
                    ("00.00", "0% (Normal)"),
                    ("-0.08", "-8% (Dark)"),
                    ("-0.16", "-16% (Darker)"),
                    ("-0.24", "-24% (Darkest)"),
                ],
            ),
            (
                "EFGlossAdjust",
                "Glossy",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFImageSmooth",
                "Image Smoothing",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFIQHTTxEnhance",
                "Halftone Text Enhancement",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFIQApplyEnhanceTo",
                "Apply Enhancements To",
                [
                    ("", "— printer default —"),
                    ("TEXTGRAPHICS", "Text & Graphics"),
                    ("TEXTGRAPHICSIMAG", "Text, Graphics & Images"),
                ],
            ),
            (
                "EFIQTxSmoothEnhance",
                "Text Smoothing",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFPreventTextBlur",
                "Color Text Blur Prevention",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFIQTxThinning",
                "Text Thinning",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
        ],
    ),

    # ── Color — Profiles & Rendering ─────────────────────────────────────────
    (
        "Color — Profiles & Rendering",
        [
            (
                "EFRGBOverride",
                "RGB Source Profile",
                [
                    ("", "— printer default —"),
                    ("EFRGBOverrideDEF", "Fiery Default"),
                    ("SRGB", "sRGB"),
                    ("ADOBERGB", "Adobe RGB"),
                    ("ECIRGB", "ECI RGB"),
                    ("APPLE13", "Apple RGB"),
                    ("FIERYRGB", "Fiery RGB"),
                    ("EFIRGB", "EFI RGB"),
                ],
            ),
            (
                "EFEmbeddedRGB",
                "Use RGB Embedded Profiles",
                [
                    ("", "— printer default —"),
                    ("EFEmbeddedRGBDEF", "Fiery Default"),
                    ("ON", "On"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFColorRendDict",
                "RGB Rendering Intent",
                [
                    ("", "— printer default —"),
                    ("EFColorRendDictDEF", "Fiery Default"),
                    ("PHOTOGRAPHIC", "Photographic"),
                    ("PRESENTATION", "Presentation"),
                    ("RELATIVE", "Relative Colorimetric"),
                    ("ABSOLUTE", "Absolute Colorimetric"),
                ],
            ),
            (
                "EFRGBSep",
                "Separate RGB/Lab to CMYK",
                [
                    ("", "— printer default —"),
                    ("EFRGBSepDEF", "Fiery Default"),
                    ("SEPSIM", "Simulation"),
                    ("SEPOUT", "Output Profile"),
                ],
            ),
            (
                "EFKOnlyGrayRGB",
                "Print RGB Gray Using Black Only",
                [
                    ("", "— printer default —"),
                    ("EFKOnlyGrayRGBDEF", "Fiery Default"),
                    ("OFF", "Off"),
                    ("TEXTGRAPHICS", "Text & Graphics"),
                    ("TEXTGRAPHICSIMAG", "Text, Graphics & Images"),
                ],
            ),
            (
                "EFEmbeddedCMYK",
                "Use CMYK Embedded Profiles",
                [
                    ("", "— printer default —"),
                    ("EFEmbeddedCMYKDEF", "Fiery Default"),
                    ("ON", "On"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFCMYKColorRendDict",
                "CMYK Rendering Intent",
                [
                    ("", "— printer default —"),
                    ("PHOTOGRAPHIC", "Photographic"),
                    ("PRESENTATION", "Presentation"),
                    ("RELATIVE", "Relative Colorimetric"),
                    ("ABSOLUTE", "Absolute Colorimetric"),
                    ("XGAM", "Pure Gamut"),
                ],
            ),
            (
                "EFBlackPointCompCMYK",
                "Black Point Compensation",
                [
                    ("", "— printer default —"),
                    ("EFBlackPointCompCMYKDEF", "Fiery Default"),
                    ("OFF", "Off"),
                    ("ON", "On"),
                ],
            ),
            (
                "EFKOnlyGrayCMYK",
                "Print CMYK Gray Using Black Only",
                [
                    ("", "— printer default —"),
                    ("EFKOnlyGrayCMYKDEF", "Fiery Default"),
                    ("OFF", "Off"),
                    ("TEXTGRAPHICS", "Text & Graphics"),
                    ("TEXTGRAPHICSIMAG", "Text, Graphics & Images"),
                ],
            ),
            (
                "EFGrayOverride",
                "Grayscale Source Profile",
                [
                    ("", "— printer default —"),
                    ("EFGrayOverrideDEF", "Fiery Default"),
                    ("SIMNONE", "None"),
                    ("dotgain10", "Dot Gain 10%"),
                    ("dotgain15", "Dot Gain 15%"),
                    ("dotgain20", "Dot Gain 20%"),
                    ("dotgain25", "Dot Gain 25%"),
                    ("dotgain30", "Dot Gain 30%"),
                    ("graygamma18", "Gray Gamma 1.8"),
                    ("graygamma22", "Gray Gamma 2.2"),
                ],
            ),
            (
                "EFEmbeddedGray",
                "Use Gray Embedded Profiles",
                [
                    ("", "— printer default —"),
                    ("ON", "On"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFGrayColorRendDict",
                "Grayscale Rendering Intent",
                [
                    ("", "— printer default —"),
                    ("PHOTOGRAPHIC", "Photographic"),
                    ("PRESENTATION", "Presentation"),
                    ("RELATIVE", "Relative Colorimetric"),
                    ("ABSOLUTE", "Absolute Colorimetric"),
                ],
            ),
            (
                "EFKOnlyGray",
                "Print Gray Using Black Only",
                [
                    ("", "— printer default —"),
                    ("EFKOnlyGrayDEF", "Fiery Default"),
                    ("OFF", "Off"),
                    ("TEXTGRAPHICS", "Text & Graphics"),
                    ("TEXTGRAPHICSIMAG", "Text, Graphics & Images"),
                ],
            ),
        ],
    ),

    # ── Color — Separations ───────────────────────────────────────────────────
    (
        "Color — Separations",
        [
            (
                "EFSeparations",
                "Combine Separations",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFColorSelectC",
                "Cyan (C)",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFColorSelectM",
                "Magenta (M)",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFColorSelectY",
                "Yellow (Y)",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFColorSelectK",
                "Black (K)",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
        ],
    ),

    # ── Image Enhancement ─────────────────────────────────────────────────────
    (
        "Image Enhancement",
        [
            (
                "EFImageWiseRange",
                "Apply Image Enhancement",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFImageWise_RangeType",
                "Image Enhance Range",
                [
                    ("", "— printer default —"),
                    ("AllPages", "All Pages"),
                    ("Pages", "Selected Pages"),
                    ("Sheets", "Selected Sheets"),
                ],
            ),
            (
                "EFAutoImageAdjustment",
                "Auto Image Adjustment",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("Position", "Position"),
                    ("PositionGradation", "Position + Gradation"),
                ],
            ),
        ],
    ),

    # ── Inspection & Proofing ─────────────────────────────────────────────────
    (
        "Inspection & Proofing",
        [
            (
                "EFAutoInspection",
                "Auto Inspection",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFInspectionLevel",
                "Inspection Level",
                [
                    ("", "— printer default —"),
                    ("Loose", "Loose"),
                    ("Normal", "Normal"),
                    ("Hard", "Hard"),
                ],
            ),
            (
                "EFColorGradation",
                "Color Gradation Patch",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFICCUWait",
                "Approve at Control Panel",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFLastProofJob",
                "Use Latest Proof Job",
                [
                    ("", "— printer default —"),
                    ("True", "Yes"),
                    ("False", "No"),
                ],
            ),
            (
                "EFSelectProofID",
                "Select Reference Image ID",
                [
                    ("", "— printer default —"),
                    ("True", "Yes"),
                    ("False", "No"),
                ],
            ),
            (
                "EFDeleteReference",
                "Delete Reference After Printing",
                [
                    ("", "— printer default —"),
                    ("True", "Yes"),
                    ("False", "No"),
                ],
            ),
            (
                "EFTUProfileBody",
                "Device Profile (Body)",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                ],
            ),
            (
                "EFTUProfileCover",
                "Device Profile (Cover)",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                ],
            ),
            (
                "EFBothSideAdjustment",
                "Both Side Adjustment",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
        ],
    ),

    # ── Copy Protection ───────────────────────────────────────────────────────
    (
        "Copy Protection",
        [
            (
                "EFCopyProtectMode",
                "Copy Protect Mode",
                [
                    ("", "— printer default —"),
                    ("Off", "Off"),
                    ("Copy", "Copy"),
                    ("IllegalCopy", "Illegal Copy"),
                    ("Invalid", "Invalid"),
                    ("InvalidCopy", "Invalid Copy"),
                ],
            ),
            (
                "EFCopyProtectLang",
                "Copy Protect Language",
                [
                    ("", "— printer default —"),
                    ("English", "English"),
                    ("French", "French"),
                    ("German", "German"),
                    ("Italian", "Italian"),
                    ("Japanese", "Japanese"),
                    ("Spanish", "Spanish"),
                ],
            ),
            (
                "EFCopyProtectPattern",
                "Copy Protect Pattern",
                [
                    ("", "— printer default —"),
                    ("Pattern1", "Pattern 1"),
                    ("Pattern2", "Pattern 2"),
                    ("Pattern3", "Pattern 3"),
                    ("Pattern4", "Pattern 4"),
                    ("Pattern5", "Pattern 5"),
                    ("Pattern6", "Pattern 6"),
                    ("Pattern7", "Pattern 7"),
                    ("Pattern8", "Pattern 8"),
                ],
            ),
        ],
    ),

    # ── Control & Diagnostics ────────────────────────────────────────────────
    (
        "Control & Diagnostics",
        [
            (
                "EFPostFlight",
                "Postflight",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("ReportConcise", "Report (Concise)"),
                    ("TestPage", "Test Page"),
                    ("ColorCodedJob", "Color Coded Job"),
                    ("All", "All"),
                ],
            ),
            (
                "EFControlBar",
                "Control Bar",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("Default", "Default"),
                ],
            ),
            (
                "EFTrayAlignment",
                "Tray Alignment",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFInlineFinisherOrder",
                "Pagination Order",
                [
                    ("", "— printer default —"),
                    ("RightLeft", "Right-to-Left"),
                    ("LeftRight", "Left-to-Right"),
                ],
            ),
            (
                "EFInRipImposition",
                "Server-based Imposition",
                [
                    ("", "— printer default —"),
                    ("OFF", "Off"),
                    ("ON", "On"),
                ],
            ),
            (
                "EFBypassChecks",
                "Bypass Fiery Settings Checks",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFScaleHalfSize",
                "Scale to Half Page Size",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
        ],
    ),
]


def build_fiery_sections(fiery_options: dict) -> list:
    """
    Return a list of section dicts with pre-computed selection state,
    ready to iterate in the template.

    Each section: {"title": str, "options": [{"key", "label", "choices": [(val, label, is_selected)]}]}
    """
    result = []
    for section_title, options in FIERY_OPTION_SECTIONS:
        built_opts = []
        for key, label, choices in options:
            current = fiery_options.get(key, "")
            built_choices = [(v, lbl, v == current) for v, lbl in choices]
            built_opts.append({"key": key, "label": label, "choices": built_choices})
        result.append({"title": section_title, "options": built_opts})
    return result
