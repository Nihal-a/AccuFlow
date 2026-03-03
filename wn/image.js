import { createCanvas } from 'canvas';

function wrapText(ctx, text, maxWidth) {
    if (!text) return [""];
    const words = String(text).split(/\s+/);
    const lines = [];
    let currentLine = words[0];

    for (let i = 1; i < words.length; i++) {
        const word = words[i];
        const width = ctx.measureText(currentLine + " " + word).width;
        if (width < maxWidth) {
            currentLine += " " + word;
        } else {
            lines.push(currentLine);
            currentLine = word;
        }
    }
    lines.push(currentLine);
    return lines;
}

export async function generateTradeTable(customer) {
    const width = 800;
    const padding = 10;
    const headerHeight = 35;
    const minRowHeight = 30;
    const themeBlue = '#5b7a9d';
    const borderGrey = '#999999';
    const textDark = '#333333';
    const white = '#ffffff';

    const transactions = customer.transactions || [];

    // We need a dummy context to measure text for height calculation
    const dummyCanvas = createCanvas(width, 100);
    const dummyCtx = dummyCanvas.getContext('2d');
    dummyCtx.font = '12px Arial';

    const colWidths = [35, 45, 300, 70, 70, 90, 90, 100];
    const colLabels = ['S.No', 'Type', 'Descriptions', 'Qty', 'Rate', 'Debit', 'Credit', 'Balance'];

    // Pre-calculate row heights
    const rowDataArray = transactions.map((tx, i) => {
        const descLines = wrapText(dummyCtx, tx.details || '-', colWidths[2] - 10);
        const height = Math.max(minRowHeight, descLines.length * 15 + 10);
        return { tx, descLines, height, sn: (i + 1).toString() };
    });

    const totalTableHeight = rowDataArray.reduce((acc, row) => acc + row.height, 0) + minRowHeight * 2; // + HeaderRow + TotalRow
    const totalHeight = totalTableHeight + headerHeight + padding * 2;

    const canvas = createCanvas(width, totalHeight);
    const ctx = canvas.getContext('2d');

    // 2. Setup Base
    ctx.fillStyle = white;
    ctx.fillRect(0, 0, width, totalHeight);

    const getX = (colIndex) => {
        let x = padding;
        for (let i = 0; i < colIndex; i++) x += colWidths[i];
        return x;
    };

    const drawVerticalLines = (y, h) => {
        ctx.strokeStyle = borderGrey;
        ctx.lineWidth = 0.5;
        colWidths.forEach((w, i) => {
            const x = getX(i);
            ctx.beginPath();
            ctx.moveTo(x, y);
            ctx.lineTo(x, y + h);
            ctx.stroke();
        });
        ctx.beginPath();
        ctx.moveTo(width - padding, y);
        ctx.lineTo(width - padding, y + h);
        ctx.stroke();
    };

    // 3. Opening Balance Bar
    ctx.fillStyle = themeBlue;
    ctx.fillRect(padding, padding, width - padding * 2, headerHeight);
    ctx.fillStyle = white;
    ctx.font = 'bold 13px Arial';
    ctx.textAlign = 'right';
    ctx.fillText('Opening Balance', getX(4), padding + 22);
    ctx.fillText(customer.opening_balance || '0.00', width - padding - 15, padding + 22);

    // 4. Table Header
    const headerY = padding + headerHeight;
    ctx.fillStyle = themeBlue;
    ctx.fillRect(padding, headerY, width - padding * 2, minRowHeight);
    drawVerticalLines(headerY, minRowHeight);
    ctx.fillStyle = white;
    ctx.font = 'bold 12px Arial';
    ctx.textAlign = 'center';
    colLabels.forEach((label, i) => {
        ctx.fillText(label, getX(i) + colWidths[i] / 2, headerY + 20);
    });

    // 5. Data Rows
    let currentY = headerY + minRowHeight;
    ctx.font = '12px Arial';

    let totalQty = 0;
    let totalDebit = 0;
    let totalCredit = 0;

    rowDataArray.forEach((row, i) => {
        // Draw Row Border
        ctx.strokeStyle = borderGrey;
        ctx.strokeRect(padding, currentY, width - padding * 2, row.height);
        drawVerticalLines(currentY, row.height);

        ctx.fillStyle = textDark;
        const tx = row.tx;

        // S.No
        ctx.textAlign = 'center';
        ctx.fillText(row.sn, getX(0) + colWidths[0] / 2, currentY + 20);

        // Type
        ctx.fillText(tx.type || 'JL', getX(1) + colWidths[1] / 2, currentY + 20);

        // Descriptions (Wrapped)
        ctx.textAlign = 'left';
        row.descLines.forEach((line, lineIdx) => {
            ctx.fillText(line, getX(2) + 5, currentY + 15 + (lineIdx * 15));
        });

        // Other Columns (Centered vertically in row)
        ctx.textAlign = 'center';
        const midY = currentY + 20;
        ctx.fillText(tx.qty || '', getX(3) + colWidths[3] / 2, midY);
        ctx.fillText(tx.rate || '', getX(4) + colWidths[4] / 2, midY);
        ctx.fillText(tx.debit || '', getX(5) + colWidths[5] / 2, midY);
        ctx.fillText(tx.credit || '', getX(6) + colWidths[6] / 2, midY);
        ctx.fillText(tx.balance || '', getX(7) + colWidths[7] / 2, midY);

        totalQty += parseFloat(String(tx.qty).replace(/,/g, '')) || 0;
        totalDebit += parseFloat(String(tx.debit).replace(/,/g, '')) || 0;
        totalCredit += parseFloat(String(tx.credit).replace(/,/g, '')) || 0;

        currentY += row.height;
    });

    // 6. Total Row
    ctx.fillStyle = themeBlue;
    ctx.fillRect(padding, currentY, width - padding * 2, minRowHeight);
    drawVerticalLines(currentY, minRowHeight);
    ctx.fillStyle = white;
    ctx.font = 'bold 12px Arial';
    ctx.textAlign = 'right';
    ctx.fillText('Total', getX(2) + colWidths[2] - 10, currentY + 20);
    ctx.textAlign = 'center';
    ctx.fillText(totalQty.toFixed(2), getX(3) + colWidths[3] / 2, currentY + 20);
    ctx.fillText(totalDebit.toFixed(2), getX(5) + colWidths[5] / 2, currentY + 20);
    ctx.fillText(totalCredit.toFixed(2), getX(6) + colWidths[6] / 2, currentY + 20);
    ctx.fillText(customer.balance || '0.00', getX(7) + colWidths[7] / 2, currentY + 20);

    return canvas.toBuffer('image/png');
}
